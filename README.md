# gitea-signoff

Local CI. Sign off on your own work.

CI is slow. Sometimes you just want a human to vouch for a commit. `gitea-signoff` writes a `signoff` commit status to Gitea, and (optionally) makes that status a required check on a branch. You become the CI.

It is a single bash script that shells out to [`tea`](https://gitea.com/gitea/tea) for authenticated API calls, so auth and host resolution come from your existing `tea login`. No tokens to wrangle.

## Credit

This is an independent, from-scratch port of Basecamp's [`gh-signoff`](https://github.com/basecamp/gh-signoff) (for GitHub). The idea is theirs; none of their code was used. Go read their write-up, it explains the "why" better than this README will.

## Requirements

- [`tea`](https://gitea.com/gitea/tea) (Gitea CLI), logged in: `tea login add`
- `jq`
- `git`

## Install

Drop the script on your `PATH`:

```
install -m 0755 gitea-signoff ~/.local/bin/gitea-signoff
```

## Usage

```
gitea-signoff                       # sign off the current commit (context: signoff)
gitea-signoff frontend              # sign off with context signoff/frontend
gitea-signoff -f                    # sign off even with a dirty/unpushed tree

gitea-signoff install [branch] [context]     # require the signoff status on a branch
gitea-signoff uninstall [branch] [context]   # stop requiring it
gitea-signoff check [branch]        # is signoff required on the branch?
gitea-signoff status [branch]       # signoff status of the current commit
```

`branch` defaults to the repo's default branch. `context` becomes `signoff/<context>`; omit it for the plain `signoff` context.

By default signing off refuses to run with uncommitted or unpushed changes, so the status attaches to a commit the server actually has. Pass `-f` to override.

### Multiple Gitea instances

Host and login are discovered from the repo's remote. To force a specific `tea` login:

```
gitea-signoff --login work install
# or
GITEA_SIGNOFF_LOGIN=work gitea-signoff status
```

## How it works

- **Sign off** → `POST /repos/{owner}/{repo}/statuses/{sha}` with `state: success`, `context: signoff`.
- **install/uninstall** → merges/removes the context in `/repos/{owner}/{repo}/branch_protections/{branch}` (`enable_status_check`, `status_check_contexts`) without clobbering other required checks.
- **status/check** → reads the branch protection's required `signoff*` contexts and the commit's combined status.

## Tests

```
./test.sh
```

Covers the pure logic (context naming, state symbols). The API paths need a live Gitea repo and are exercised manually.
