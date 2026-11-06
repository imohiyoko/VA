# 参考 8: 悪意の有無（システムが利用者を裏切っていないか）

> 実際の実行は `scripts/va.py` と `checklists/malicious-code.md` が担う。ここは人が読むための背景説明。

脆弱性診断は「外の攻撃者がこのコードを悪用できるか」を問う。この観点は別の問いで、
**「このコード自身（作者・依存パッケージ・CI）が、利用者や運用者に対して悪意のある動きをしていないか」**を問う。
攻撃者の入力は要らない。インストールした・ビルドした・起動しただけで害が出るものを探す。

## 見るもの

| category | 例 |
|---|---|
| `backdoor` | 特定の値・ヘッダ・日時で認証を素通り、隠しコマンド、リバースシェル |
| `data-exfiltration` | 環境変数・トークン・利用者データを、目的と無関係なハードコードの宛先へ送る |
| `credential-harvesting` | `~/.ssh`、`~/.aws`、ブラウザのプロファイル、他アプリのトークンを読む・入力を横取りする |
| `obfuscated-payload` | base64・hex・XOR 等で隠したコードを実行、ダウンロードしたものを実行（`curl \| sh`） |
| `malicious-install-hook` | `postinstall`、`setup.py`、`build.rs`、Makefile、git フック、`conftest.py` が通信・コード実行をする |
| `suspicious-ci` | ワークフローがシークレットを外部に送る、目的外の外部スクリプトを実行、成果物を目立たず書き換える |
| `malicious-dependency` | タイポスクワッティング、見慣れないレジストリ・Git URL、osv-scanner の `MAL-` advisory |
| `destructive-payload` | 条件付きのデータ削除・暗号化、マイニング等の資源の食い潰し |

## 仕組み

- **チェックリスト**: `malicious-code` は `tags: [always]` なので、レビューするすべてのファイルに適用される
- **要約**: 要約タスクが `malice_suspect` を立てたファイルは risk 3（最優先）でレビューする
  （`malice_suspect` を持たない古い索引は、次の run で1回だけ要約し直す）
- **強制レビュー**: インストール・ビルド・コミット時に自動で動くファイルと依存の宣言（`package.json`、`setup.py`、
  `pyproject.toml`、`build.rs`、Makefile、Dockerfile、`conftest.py`、`go.mod`、`requirements*.txt`、`.husky/`、`.githooks/`、
  `.github/workflows/` など）は、要約の評価にかかわらず risk 2 以上
- **diff モード**: 変更されたファイルは risk 0 でもすべてレビューする（悪意のある変更は無害に見えるファイルに紛れ込むため）
- **依存**: osv-scanner の `MAL-` で始まる advisory は既知の悪意あるパッケージとして `malicious-dependency`（critical、`likely`）にする。
  到達性は問わない（インストールした時点で動くため）
- **攻撃者**: これらの finding の `attacker` は `code-author`（コード・依存・CI の作者自身）
- **トリアージ**: 「本当にそう動くか」と「目的から説明できず隠れているか（設定で切れない・文書がない・宛先が固定・中身が符号化）」を確認する。
  文書化され設定で切れる機能（明示されたテレメトリ、更新確認など）は `false_positive`
- **レポート**: `report.md` の「Malicious-intent check」節に、確認したファイル数・索引が疑ったファイル・該当 finding を、
  ゼロ件でも必ず書く（見ていないのか、見て無かったのかを区別するため）

## 限界

- 静的に読むだけなので、実行時に取得するコード・暗号化された中身・バイナリの中は分からない（中身が見えないこと自体を `obfuscated-payload` として出す）
- 索引されない拡張子・大きすぎるファイル・バイナリは見ていない（report の Not covered）
- 依存パッケージの中身（`node_modules` 等）は読まない。既知の悪意あるパッケージは osv-scanner の `MAL-` で拾う
