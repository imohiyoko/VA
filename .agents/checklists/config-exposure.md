---
id: config-exposure
tags: [config, secrets]
langs: [any]
categories: [hardcoded-secret, debug-exposure, insecure-default, sensitive-logging]
---
- 本番設定で `DEBUG=True` 等が有効、または環境変数が無いときの既定値が危険（デバッグ有効・認証無効・空の秘密鍵）
- デフォルトの認証情報（`admin/admin` 等）が使われうる
- ログにパスワード・トークン・個人情報を出力している
- シークレットを設定ファイルにリテラルで書いている（値は書かない）
