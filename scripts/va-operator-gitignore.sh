#!/usr/bin/env bash
# 運用リポジトリ用: 上流 .gitignore の「va:operator-data」ブロックを取り除き、operator/ を追跡できるようにする。
# 何度実行しても同じ結果になる。
set -euo pipefail
f="${1:-.gitignore}"
[ -f "$f" ] || exit 0
tmp="$(mktemp)"
awk '
  /^# >>> va:operator-data/ { skip=1; print "# (va:operator-data block removed: this is an operator repository)"; next }
  /^# <<< va:operator-data/ { skip=0; next }
  !skip
' "$f" | awk '!(/^# \(va:operator-data block removed/ && seen++)' > "$tmp"
mv "$tmp" "$f"
