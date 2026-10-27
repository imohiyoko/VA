#!/usr/bin/env bash
# 上流（public）へ出す差分に、運用データ・対象を特定できる語・シークレットが含まれていないか確認する。
#
#   scripts/va-sanitize-check.sh <repo-dir> <base-ref|EMPTY> [denylist-file] [extra-text-file]
#
# denylist-file: 1行1語（大文字小文字無視の固定文字列）。'#' で始まる行と空行は無視。
#                運用リポジトリの operator/sanitize-denylist.txt を渡す（このファイル自体は public に出さない）。
#                指定したのに読めない場合は失敗する（exit 2）。省略するときは空文字列ではなく引数ごと省く。
# extra-text-file: 差分と同じ検査（denylist・シークレット・fingerprint）にかける追加のテキスト（PR のタイトル・本文など）。
# 範囲内のコミットメッセージも同じ検査にかける（public に出るため）。
set -euo pipefail
repo="$1"; base="$2"; deny_given=$(( $# >= 3 )); deny="${3:-}"; extra="${4:-}"
if [ "$deny_given" -eq 1 ] && { [ -z "$deny" ] || [ ! -f "$deny" ] || [ ! -r "$deny" ]; }; then
  echo "SANITIZE: denylist '$deny' is not a readable file" >&2; exit 2
fi
if [ -n "$extra" ] && { [ ! -f "$extra" ] || [ ! -r "$extra" ]; }; then
  echo "SANITIZE: extra text '$extra' is not a readable file" >&2; exit 2
fi
# cd の前に絶対パスにする
[ -n "$deny" ] && deny="$(cd "$(dirname "$deny")" && pwd)/$(basename "$deny")"
[ -n "$extra" ] && extra="$(cd "$(dirname "$extra")" && pwd)/$(basename "$extra")"
fail=0
err() { echo "SANITIZE: $*" >&2; fail=1; }

cd "$repo"
# base: コミット（3点 diff）か EMPTY（リポジトリ全体を検査）
if [ "$base" = "EMPTY" ]; then
  range=("$(git hash-object -t tree /dev/null)" HEAD)
elif git rev-parse -q --verify "$base^{commit}" >/dev/null; then
  range=("$base...HEAD")
else
  echo "SANITIZE: invalid base '$base'" >&2; exit 2
fi
files="$(git diff --name-only "${range[@]}"; git diff --name-only; git ls-files --others --exclude-standard)" || exit 2
diff_text="$(git diff "${range[@]}"; git diff)" || exit 2
# 途中のコミットで足して後で消した内容も公開履歴に残るので、コミットごとの差分も検査する
if [ "$base" = "EMPTY" ]; then hist="$(git log -p --format= HEAD)" || exit 2
else hist="$(git log -p --format= "$base..HEAD")" || exit 2; fi
diff_text="$diff_text
$hist"
# 追加行（ファイルヘッダの '+++ ' は除き、'+' で始まる内容の行は含める）
added="$(printf '%s\n' "$diff_text" | awk '/^diff --git /{h=1} /^@@/{h=0; next} !h && /^\+/' || true)"
# コミットメッセージと追加テキストも public に出る
if [ "$base" = "EMPTY" ]; then msgs="$(git log --format=%B HEAD)" || exit 2
else msgs="$(git log --format=%B "$base..HEAD")" || exit 2; fi
added="$added
$msgs"
if [ -n "$extra" ]; then added="$added
$(cat "$extra")"; fi

# 1. 運用データのパス
if printf '%s\n' "$files" | grep -E '^(operator/|work/)' >/dev/null; then
  err "operator/ or work/ files are in the diff:"; printf '%s\n' "$files" | grep -E '^(operator/|work/)' >&2
fi

# 2. 運用側の非公開語リスト
if [ -n "$deny" ]; then
  while IFS= read -r term || [ -n "$term" ]; do
    term="${term%%$'\r'}"
    [[ -z "$term" || "$term" == \#* ]] && continue
    if printf '%s\n' "$added" "$files" | grep -iF -- "$term" >/dev/null; then
      err "denylisted term found: '${term:0:3}…' (see your denylist)"
    fi
  done < "$deny"
fi

# 3. シークレットらしき文字列
pat='(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9_-]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.)'
if printf '%s\n' "$added" | grep -E -- "$pat" >/dev/null; then
  err "secret-like string in added lines"
fi

# 4. finding の fingerprint らしき16桁 hex が大量にある（findings の貼り付けの疑い）
n=$(printf '%s\n' "$added" | grep -oE '\b[0-9a-f]{16}\b' | wc -l || true)
if [ "${n:-0}" -gt 3 ]; then err "many 16-hex ids in added lines (pasted findings?)"; fi

if [ "$fail" -ne 0 ]; then echo "sanitize check FAILED" >&2; exit 1; fi
echo "sanitize check passed"
