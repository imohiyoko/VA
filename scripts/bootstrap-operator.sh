#!/usr/bin/env bash
# 運用リポジトリを初期化する。運用リポジトリの clone のルートで実行する。
#
#   /path/to/VA/scripts/bootstrap-operator.sh [upstream-url]
#
# - VA を upstream リモートとして登録し、履歴ごとマージする（以後 git merge upstream/main で同期できる）
# - templates/operator/ の雛形（ワークフロー、operator/ 設定）を、まだ無いものだけ配置する
# - .gitignore の運用データ除外ブロックを外す
set -euo pipefail
UPSTREAM="${1:-https://github.com/imohiyoko/VA.git}"
BRANCH="${VA_UPSTREAM_BRANCH:-main}"

git rev-parse --is-inside-work-tree >/dev/null
[ -z "$(git status --porcelain)" ] || { echo "working tree is not clean" >&2; exit 1; }

if git remote get-url upstream >/dev/null 2>&1; then
  git remote set-url upstream "$UPSTREAM"
else
  git remote add upstream "$UPSTREAM"
fi
git fetch upstream "$BRANCH"

# 既存の README は operator/README.md に退避（上流の README と衝突し続けないように）
if git cat-file -e HEAD:README.md 2>/dev/null && ! git cat-file -e HEAD:operator/README.md 2>/dev/null; then
  mkdir -p operator
  git mv README.md operator/README.md
  git commit -qm "Move operator README under operator/"
fi

if ! git merge-base --is-ancestor "upstream/$BRANCH" HEAD 2>/dev/null; then
  git merge --no-edit --allow-unrelated-histories "upstream/$BRANCH" -m "Merge VA upstream" || {
    echo "merge conflict: resolve, commit, then re-run this script" >&2; exit 1; }
fi

# 雛形の配置（既にあるファイルは上書きしない）
(cd templates/operator && find . -type f) | while read -r f; do
  dest="${f#./}"
  if [ ! -e "$dest" ]; then mkdir -p "$(dirname "$dest")"; cp "templates/operator/$dest" "$dest"; echo "added $dest"; fi
done

bash scripts/va-operator-gitignore.sh .gitignore
git add -A
git diff --cached --quiet || git commit -qm "Bootstrap VA operator repository"
echo
echo "Done. Next:"
echo "  1. Edit operator/va.toml (targets) and operator/sanitize-denylist.txt"
echo "  2. Add repository secrets: CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY, VA_TARGETS_TOKEN, VA_UPSTREAM_TOKEN"
echo "  3. git push"
