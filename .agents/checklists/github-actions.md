---
id: github-actions
tags: [ci]
langs: [yaml]
categories: [ci-injection, ci-permissions, ci-pwn-request, ci-unpinned-action]
---
- `run:` の中に `${{ github.event.* }}`（issue/PR のタイトル・本文、ブランチ名、コメント）を直接埋め込んでいるか → `ci-injection`
  - 安全: `env:` に入れて `"$VAR"` で参照
- `pull_request_target` / `workflow_run` で PR 側のコード（`github.event.pull_request.head.*`）を checkout して実行しているか → `ci-pwn-request`
- `permissions:` が無い、または `write-all` → `ci-permissions`（low）
- サードパーティ action をタグやブランチで参照しているか（`@v1`, `@main`）→ `ci-unpinned-action`（low）。`actions/*` と `github/*` は info
