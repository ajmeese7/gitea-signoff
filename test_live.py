#!/usr/bin/env python3
"""Opt-in tests against a disposable repository on a real Gitea instance."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
import uuid

HOST = os.environ.get("GITEA_SIGNOFF_TEST_HOST")
SCRIPT = Path(__file__).with_name("gitea-signoff")


@unittest.skipUnless(HOST, "set GITEA_SIGNOFF_TEST_HOST to a real test instance")
class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner = cls.api("user")["login"]
        cls.name = f"signoff-test-{uuid.uuid4().hex[:12]}"
        cls.repository = cls.api("user/repos", "POST", {
            "name": cls.name, "private": True, "default_branch": "test-main",
        })
        cls.path = f"repos/{cls.owner}/{cls.name}"
        cls.addClassCleanup(cls.api, cls.path, "DELETE")
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.git("init", "-q", "-b", "test-main")
        cls.git("config", "user.email", "signoff-test@example.com")
        cls.git("config", "user.name", "Signoff Test")
        cls.git("config", "commit.gpgsign", "false")
        cls.git("commit", "-qm", "fixture", "--allow-empty")
        cls.git("remote", "add", "origin", cls.repository["ssh_url"])
        cls.git("push", "-qu", "origin", "test-main")
        cls.git("checkout", "-qb", "feature")
        cls.git("commit", "-qm", "feature", "--allow-empty")
        cls.git("push", "-qu", "origin", "feature")
        cls.sha = cls.git("rev-parse", "HEAD")

    @classmethod
    def api(cls, path, method="GET", body=None):
        args = ["gt", "--host", HOST, "--no-input", "api", path, "-X", method]
        data = None
        if body is not None:
            args += ["--input", "-"]
            data = json.dumps(body)
        result = subprocess.run(args, input=data, capture_output=True, text=True, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else None

    @classmethod
    def git(cls, *args):
        return subprocess.check_output(["git", *args], cwd=cls.root, stderr=subprocess.PIPE, text=True).strip()

    def signoff(self, *args, **kwargs):
        return subprocess.run(self.command(*args), cwd=self.root, capture_output=True, text=True, check=False, **kwargs)

    def command(self, *args):
        return ["bash", str(SCRIPT), "--host", HOST, "--repo", self.repository["html_url"], *args]

    def latest(self, context):
        statuses = self.api(f"{self.path}/statuses/{self.sha}")
        return next((s["status"] for s in statuses if s["context"] == f"signoff/{context}"), None)

    def test_success_then_failure_replaces_green(self):
        self.assertEqual(self.signoff("run", "lifecycle", "--", "true").returncode, 0)
        self.assertEqual(self.latest("lifecycle"), "success")
        result = self.signoff("run", "lifecycle", "--", "bash", "-c", "exit 7")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(self.latest("lifecycle"), "failure")

    def test_dirty_tree_never_runs_command_or_posts_success(self):
        dirty = self.root / "dirty"
        dirty.write_text("uncommitted")
        try:
            result = self.signoff("run", "dirty", "--", "touch", "should-not-exist")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.root / "should-not-exist").exists())
            self.assertIsNone(self.latest("dirty"))
        finally:
            dirty.unlink()

    def test_changed_tree_cannot_be_signed_off(self):
        try:
            result = self.signoff("run", "changed", "--", "touch", "changed")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.latest("changed"), "failure")
        finally:
            (self.root / "changed").unlink(missing_ok=True)

    def test_invalid_index_cannot_be_signed_off(self):
        env = dict(os.environ, GIT_INDEX_FILE="/dev/null")
        result = self.signoff("run", "index", "--", "true", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(self.latest("index"))

    def test_head_change_records_failure_on_original_sha(self):
        try:
            result = self.signoff("run", "head", "--", "git", "commit", "-qm", "during checks", "--allow-empty")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.latest("head"), "failure")
            new_sha = self.git("rev-parse", "HEAD")
            self.assertNotEqual(new_sha, self.sha)
            self.assertEqual(self.api(f"{self.path}/statuses/{new_sha}"), [])
        finally:
            self.git("reset", "--hard", self.sha)

    def test_protection_contexts_are_preserved_and_disabled_is_not_required(self):
        self.assertEqual(self.signoff("install", "test-main", "local-ci").returncode, 0)
        self.api(f"{self.path}/branch_protections/test-main", "PATCH", {
            "status_check_contexts": ["signoff/local-ci", "unrelated"],
        })
        result = self.signoff("install", "test-main", "other")
        self.assertEqual(result.returncode, 0, result.stderr)
        rule = self.api(f"{self.path}/branch_protections/test-main")
        self.assertEqual(set(rule["status_check_contexts"]), {"signoff/local-ci", "signoff/other", "unrelated"})
        self.assertNotEqual(self.signoff("status", "test-main").returncode, 0)
        for context in ("local-ci", "other"):
            result = self.signoff("run", context, "--", "true")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.signoff("status", "test-main").returncode, 0)
        self.api(f"{self.path}/branch_protections/test-main", "PATCH", {"enable_status_check": False})
        self.assertNotEqual(self.signoff("check", "test-main").returncode, 0)
        self.assertEqual(self.signoff("status", "test-main").returncode, 0)
        self.assertEqual(self.signoff("uninstall", "test-main", "local-ci").returncode, 0)
        rule = self.api(f"{self.path}/branch_protections/test-main")
        self.assertFalse(rule["enable_status_check"])
        self.assertEqual(set(rule["status_check_contexts"]), {"signoff/other", "unrelated"})

    def test_status_reads_paginated_history(self):
        self.assertEqual(self.signoff("install", "pagination", "paged").returncode, 0)
        for number in range(55):
            self.api(f"{self.path}/statuses/{self.sha}", "POST", {
                "context": "signoff/paged" if number == 0 else f"padding/{number}",
                "state": "success", "description": "pagination fixture",
            })
        result = self.signoff("status", "pagination")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.api(f"{self.path}/statuses/{self.sha}", "POST", {
            "context": "signoff/paged", "state": "failure",
        })
        self.assertNotEqual(self.signoff("status", "pagination").returncode, 0)

    def test_protection_read_authentication_error_fails_closed(self):
        env = dict(os.environ, GITEA_TOKEN="deliberately-invalid-test-token",
                   GITEA_SIGNOFF_HOST=HOST, GITEA_CLI_HOST=HOST)
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; REPO="$2"; cmd_status test-main',
             "_", str(SCRIPT), self.repository["html_url"]],
            cwd=self.root, env=env, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("no signoff required", result.stdout)

    def test_remote_rewrite_invalidates_cached_upstream(self):
        base = self.git("rev-parse", "HEAD^")
        self.git("push", "-q", "origin", f"{base}:refs/heads/feature", "--force")
        try:
            # Recreate the stale cached upstream that older code trusted.
            self.git("update-ref", "refs/remotes/origin/feature", self.sha)
            result = self.signoff("run", "rewritten", "--", "true")
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(self.latest("rewritten"))
        finally:
            self.git("push", "-q", "origin", "HEAD:refs/heads/feature")

    def test_term_stops_advertised_pid_and_child(self):
        child_pid = self.root / ".git" / "child-pid"
        proc = subprocess.Popen(self.command("run", "term", "--", "bash", "-c", f'echo $$ > "{child_pid}"; exec sleep 120'), cwd=self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 20
            while not child_pid.exists():
                if proc.poll() is not None or time.monotonic() > deadline:
                    self.fail("command did not start")
                time.sleep(0.1)
            self.assertEqual(self.latest("term"), "pending")
            proc.send_signal(signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=20)
            self.assertNotEqual(proc.returncode, 0, stdout + stderr)
            self.assertEqual(self.latest("term"), "failure")
            pid = int(child_pid.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.communicate(timeout=20)


if __name__ == "__main__":
    unittest.main()
