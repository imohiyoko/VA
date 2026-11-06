---
id: malicious-code
tags: [always]
langs: [any]
categories: [backdoor, data-exfiltration, credential-harvesting, obfuscated-payload, malicious-install-hook, suspicious-ci, malicious-dependency, destructive-payload]
---
この観点だけは「攻撃者の入力がどこに届くか」ではなく、**コード自身（作者・依存・CI）が利用者を裏切っていないか**を問う。ファイルの目的（要約）から説明できない挙動を探し、evidence には「何をするか・どこへ送るか・なぜ目的から説明できないか」を書く。正当な理由が読み取れるなら出さない。

- 特定の値・ヘッダ・ユーザー名・日時・環境変数のときだけ認証や権限チェックを素通りさせる、隠しコマンドやリモートシェルを開く → `backdoor`
  - 安全: 設定で明示的に有効化し、ドキュメントに書かれたテスト用モード
- 環境変数・ファイル・Cookie・トークン・利用者データを、目的と無関係な外部ホスト（ハードコードの URL/IP、DNS、ペーストサイト、Webhook）へ送る → `data-exfiltration`
  - 安全: 設定で宛先を変えられ、目的から説明できる API 呼び出し・明示されたテレメトリ
- `~/.ssh`、`~/.aws`、`.npmrc`、`.git-credentials`、ブラウザのプロファイル、キーチェーン、他アプリのトークンを読む、またはパスワード入力を横取り・記録する → `credential-harvesting`
- base64/hex/文字コード配列・圧縮・XOR などで中身を隠したコードを `eval`/`exec`/`Function`/`subprocess` で実行する、またはダウンロードしたものを実行する（`curl | sh` 等） → `obfuscated-payload`
- `postinstall`/`preinstall`/`prepare`、`setup.py`、`build.rs`、Makefile、git フック、`conftest.py` 等、インストール・ビルド・テストの時に自動で動く処理が、ネットワーク通信・ファイル外の書き込み・コード実行をする → `malicious-install-hook`
- CI ワークフローがシークレットや `GITHUB_TOKEN` を外部へ送る、目的外の外部スクリプトを取得して実行する、リリース成果物やブランチを目立たない形で書き換える → `suspicious-ci`
- 依存の宣言に、有名パッケージに似せた名前（タイポスクワッティング）、見慣れないレジストリ・Git URL・個人のフォーク、固定されていない URL 取得がある → `malicious-dependency`
- 条件付き（日時・ロケール・IP・回数）でファイルやデータを消す・暗号化する・資源を食い潰す（マイニング等） → `destructive-payload`
