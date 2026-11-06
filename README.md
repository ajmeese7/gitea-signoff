# gitea-signoff

Local CI and human signoff for Gitea. Publish a commit status, and optionally require it before merging.

A single Bash script using [`gt`](https://gitea.com/gitea/cli) for authenticated API calls and repository discovery. No tokens to wrangle.

## Requirements

- `gt` 1.1.0 or later, authenticated with `gt auth login`
- Bash, `jq`, Git
- Repository write access for statuses; repository administration for protection changes

## Install

```sh
install -m 0755 gitea-signoff ~/.local/bin/gitea-signoff
```

## Run local checks

Push the branch with an upstream first, then run your project's checks:

```sh
gitea-signoff run local-ci -- ./scripts/check-project.sh
```

This posts `signoff/local-ci` as pending, runs the command with its original arguments, and publishes success only after exit zero and a second check of the clean working tree, HEAD and live upstream SHA. Failure or interruption records failure on the original SHA. A failed rerun replaces an earlier green result. If Gitea cannot accept the final status, the command fails and reports the error; an interrupted network request can leave a pending status, never an inferred success. Force mode is unavailable for `run`.

Commands run as child process groups so terminating the signoff process also terminates their ordinary descendants. SIGKILL and host failure cannot run cleanup; pending then remains pending. Local checks must keep generated logs and build output ignored by Git, and must not change tracked inputs. The command owns its log retention; stdout and stderr pass through unchanged.

A local status is an attestation from the authenticated account, not independent evidence that the checks ran. Keep independent post-merge CI if that distinction matters to your workflow. These statuses are unrelated to Git's `Signed-off-by` trailers or cryptographic commit signing.

## Human signoff

```sh
gitea-signoff                 # signoff on current HEAD
gitea-signoff frontend        # signoff/frontend
gitea-signoff -f              # explicitly bypass clean/published checks for human signoff
```

Ordinary signoff requires a clean attached branch whose upstream currently points to HEAD, and verifies that SHA exists in the selected Gitea repository. It does not execute checks. Extra positional arguments are rejected so an accidental command cannot silently become a human signoff.

## Require a status

```sh
gitea-signoff install master local-ci
gitea-signoff check master
gitea-signoff status master
gitea-signoff uninstall master local-ci
```

Omitting the branch uses the repository default. Omitting the context uses `signoff`. Install/uninstall preserve unrelated required contexts and other protection fields. They do not remove existing runner requirements: coordinate that change separately when disabling PR workflows, or merges will remain blocked waiting for them. API errors fail the command; only an explicit HTTP 404 means no protection rule.

`status` reads the newest status for each required `signoff` / `signoff/*` context, including paginated history. Disabled status protection is not reported as enforced.

## Multiple instances and accounts

Global options precede the command:

```sh
gitea-signoff --host http://gitea.example:3000 --user alice --repo team/project run local-ci -- ./check.sh
```

Defaults come from `gt`'s normal repository discovery. `GITEA_SIGNOFF_HOST`, `GITEA_SIGNOFF_USER` and `GITEA_SIGNOFF_REPO` provide equivalent overrides. The resolved repository URL is pinned before issuing status or protection requests.

## How it works

- **Human signoff** writes a success commit status for the current commit.
- **Run local checks** writes pending before executing the command, then success only if it exits successfully and the commit is still clean and published; failures and interruptions write failure.
- **Install/uninstall** adds or removes a required signoff context while preserving unrelated required contexts and other protection settings.
- **Check/status** reports whether signoff is required and whether the latest status for each required signoff context succeeded.

## Tests

```sh
./test.sh
python3 test_live.py                 # skips unless explicitly configured
GITEA_SIGNOFF_TEST_HOST=http://gitea.example:3000 python3 test_live.py -v
```

The live suite requires an authenticated account allowed to create private repositories and SSH Git access to that instance. It creates one uniquely named private repository, tests real pushes, statuses, protections, failed checks, dirty/changed HEAD, stale upstream and process termination, then deletes that repository. No production protection rule is changed. Git fixture commits are unsigned and local to the disposable repository. If setup fails before the cleanup registration, inspect the printed error before running again.

## Credit

An independent, from-scratch port of Basecamp's [`gh-signoff`](https://github.com/basecamp/gh-signoff). The idea is theirs; none of their code was used.
