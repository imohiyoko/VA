# 参考 5: CI / サプライチェーン

> 実際の実行は `scripts/va.py`（ツール実行）と `checklists/` が担う。ここは人が読むための背景説明。

## GitHub Actions
- `pull_request_target` / `workflow_run` で PR のコードを checkout・実行していないか
- `${{ github.event.* }}`（issue タイトル、PR 本文、ブランチ名など）を `run:` に直接埋め込んでいないか（スクリプトインジェクション）
- `permissions:` が未指定、または `write-all`
- サードパーティ action が SHA ではなくタグ・ブランチで参照されている
- シークレットがフォーク PR から参照できる構成、`ACTIONS_STEP_DEBUG` 等でのログ漏洩
- self-hosted runner を public リポジトリで使用

## その他
- Dockerfile: `latest` タグ、root 実行、`curl | sh`、シークレットの `ARG`/`ENV` 埋め込み
- IaC（Terraform / k8s / CloudFormation）: 公開バケット、`0.0.0.0/0` の管理ポート、過剰な IAM、特権コンテナ
- `.github/CODEOWNERS` とブランチ保護の前提が崩れていないか（分かる範囲で）
