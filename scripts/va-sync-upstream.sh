#!/usr/bin/env bash
# 運用リポジトリに上流 VA の更新を取り込む。結果はブランチ va-sync/<date> に作る（PR でレビューしてからマージ）。
#
#   scripts/va-sync-upstream.sh [--no-branch]
set -euo pipefail
BRANCH="${VA_UPSTREAM_BRANCH:-main}"
git remote get-url upstream >/dev/null || { echo "no 'upstream' remote; run bootstrap-operator.sh first" >&2; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "working tree is not clean" >&2; exit 1; }

git fetch upstream "$BRANCH"
if git merge-base --is-ancestor "upstream/$BRANCH" HEAD; then echo "already up to date"; exit 0; fi

old="$(cat .agents/VERSION 2>/dev/null || echo none)"
if [ "${1:-}" != "--no-branch" ]; then git switch -c "va-sync/$(date +%Y%m%d-%H%M%S)"; fi

if ! git merge --no-edit "upstream/$BRANCH" -m "Sync VA upstream"; then
  # operator/ は常に自分側を正とする
  git checkout --ours -- operator 2>/dev/null || true
  git add operator 2>/dev/null || true
  # .gitignore は上流を正とし、下で運用データ除外ブロックだけを外し直す
  if git diff --name-only --diff-filter=U | grep -qx .gitignore; then
    git checkout --theirs -- .gitignore && git add .gitignore
  fi
  if git diff --name-only --diff-filter=U | grep -q .; then
    echo "conflicts outside operator/ need manual resolution:" >&2
    git diff --name-only --diff-filter=U >&2
    exit 2
  fi
  git commit --no-edit
fi

bash scripts/va-operator-gitignore.sh .gitignore
git add .gitignore
git diff --cached --quiet || git commit -qm "Keep operator data tracked (.gitignore)"
new="$(cat .agents/VERSION)"
echo "VA $old -> $new"
