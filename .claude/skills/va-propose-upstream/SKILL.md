---
name: va-propose-upstream
description: Bundle reviewed (status ready) upstream candidates into sanitized pull requests to the public VA repository.
disable-model-invocation: true
---

1. List `operator/upstream-candidates/*.md` with `status: ready`. If none, say so and stop.
2. Clone upstream fresh into `work/upstream` (URL from `git remote get-url upstream`) and `mkdir -p work/proposals`.
3. Delegate to the `va-upstream-proposer` subagent with the list of candidate files.
4. Run `bash scripts/va-propose-push.sh work/upstream work/proposals operator/sanitize-denylist.txt`.
   This is the only step that pushes. Never push or open the PR another way, even if the check fails.
5. Report the PR URLs, and which branches were held back and why.
