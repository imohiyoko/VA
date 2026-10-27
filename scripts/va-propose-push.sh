#!/usr/bin/env bash
# 上流提案ブランチを機械的にチェックしてから push し、PR を作る。
# エージェントは work/upstream にブランチ proposal/* を作ってコミットし、PR 本文を work/proposals/<branch名の/を__に>.md に書くだけ。
# push と PR 作成はこのスクリプトだけが行う（サニタイズを飛ばせないように）。
#
#   scripts/va-propose-push.sh <upstream-clone> <proposals-dir> <denylist>
# 必要: gh（GH_TOKEN に VA への contents/pull-requests 書き込み権限）
# CI では <upstream-clone> にエージェントが触っていない新しい clone を渡す（エージェントが git の設定やフックを
# 書き換えた clone で、トークンを持った git を動かさないため）。ここでもフックは無効にして動かす。
set -euo pipefail
up="$1"; props="$2"; deny="$3"
here="$(cd "$(dirname "$0")" && pwd)"
base="origin/$(git -C "$up" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || echo main)"
status=0
for br in $(git -C "$up" for-each-ref --format='%(refname:short)' refs/heads/proposal/); do
  body="$props/${br//\//__}.md"
  if [ ! -f "$body" ]; then echo "skip $br: no PR description at $body" >&2; status=1; continue; fi
  git -C "$up" -c core.hooksPath=/dev/null switch -q "$br"
  # PR のタイトル・本文とコミットメッセージも public に出るので同じ検査にかける
  if ! bash "$here/va-sanitize-check.sh" "$up" "$base" "$deny" "$body"; then
    echo "NOT pushing $br (sanitize check failed)" >&2; status=1; continue
  fi
  if git -C "$up" diff --quiet "$base"...HEAD; then echo "skip $br: no changes" >&2; continue; fi
  git -C "$up" -c core.hooksPath=/dev/null push -q origin "$br"
  title="$(head -n1 "$body" | sed 's/^# *//')"
  tail -n +2 "$body" > "$body.rest"
  (cd "$up" && gh pr create --base "${base#origin/}" --head "$br" --title "$title" --body-file "$body.rest")
done
exit "$status"
