# VA への貢献

VA は public です。出したものは取り消せない前提で扱ってください。
ルールの本体は [`.agents/learning/upstream-policy.md`](../.agents/learning/upstream-policy.md)、
学習の分類は [`.agents/learning/classification.md`](../.agents/learning/classification.md) です。

## 何を出すか

| 出す | 出さない |
|---|---|
| チェックリストの追加・「安全な形」の補足（誤検知を減らす） | 対象名・パス・識別子・コード片 |
| タスクプロンプトの改善 | 診断結果そのもの |
| モデルプロファイルへの補正（根拠の数値つき） | 1回だけの観測に基づく変更 |
| スクリプトの不具合修正・機能追加 | 社内ルール（`operator/overrides.md` に置く） |

## バージョン

| 変更 | bump |
|---|---|
| findings の形式、fingerprint の算出、ディレクトリ構成 | MAJOR |
| チェックリスト・プロンプト・選定ロジックなど検出結果が変わりうるもの | MINOR（運用側で次回フルスキャン） |
| 説明の修正のみ | PATCH |

`va-guard` が、手法を変えたのに `VERSION` / `CHANGELOG.md` が更新されていない PR を止めます。

## 仕事で使っている運用リポジトリから出すとき

雇用先の情報を個人の public リポジトリへ出すことになります。所属組織のルールを確認し、
迷うものは出さないでください。denylist に社名・製品名・ドメインを必ず入れておいてください。
