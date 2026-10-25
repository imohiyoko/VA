---
id: path-traversal
tags: [filesystem]
langs: [any]
categories: [path-traversal, zip-slip, unrestricted-upload]
---
- 外部入力をファイルパスに連結して読み書き・削除しているか（`../` で基準ディレクトリ外に出られるか）
  - 安全: 正規化（`realpath`/`resolve`）した後に基準ディレクトリ配下かを確認している
- アーカイブ展開でエントリ名をそのままパスに使っているか（Zip Slip）
- アップロードされたファイル名・拡張子をそのまま保存し、Web から実行・配信できる場所に置いているか
- `send_file` / `res.sendFile` / 静的配信のルートが広すぎないか
