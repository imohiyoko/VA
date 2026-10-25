---
id: container
tags: [container]
langs: [dockerfile, yaml]
categories: [container]
---
- `USER` 指定がなく root で実行される
- ベースイメージが `latest` タグ、またはダイジェスト未固定
- `curl ... | sh` でスクリプトを実行している
- `ARG`/`ENV` にシークレットを入れている（イメージ履歴に残る）
- compose / k8s で `privileged: true`、ホストのパス・Docker ソケットのマウント
