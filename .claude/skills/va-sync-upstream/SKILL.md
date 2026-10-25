---
name: va-sync-upstream
description: Pull the latest VA (upstream) into this operator repository without losing operator data.
disable-model-invocation: true
---

1. Run `scripts/va-sync-upstream.sh`. It fetches `upstream`, merges into a branch `va-sync/<date>`,
   keeps everything under `operator/`, and re-applies the operator `.gitignore` rule.
2. If it reports conflicts outside `operator/`, resolve them in favour of upstream unless `operator/overrides.md`
   explains a local reason. Never edit upstream-owned files to keep a local tweak; move the tweak to `operator/overrides.md`.
3. Summarize what changed upstream from `.agents/CHANGELOG.md` (new version vs. the previous one) and open a PR to this repository.
4. If the MINOR version changed, mention that the next scheduled audit of every target will be a full scan.
