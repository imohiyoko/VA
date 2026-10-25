# チェックリスト

レビュータスクに渡す観点の**単一の情報源**。`scripts/va.py` がファイル要約の `tags` と言語から
該当するチェックリストだけを選んでプロンプトに入れる（小さいモデルでも焦点がぶれないように）。

## frontmatter
```yaml
id: sql-injection          # 一意
tags: [db]                 # 要約のタグにどれか1つでも一致したら適用。[always] は常に適用
langs: [any]               # any か、言語名（python, javascript, typescript, go, java, ruby, php, csharp, rust, c, cpp, shell, yaml, dockerfile, terraform）
categories: [sqli]         # この観点で出してよい finding の category
```

## 本文の書き方（小さいモデル向け）
- 1項目 = Yes/No で答えられる具体的な問い
- 「危険な形」と「安全な形」を短く対比させる
- 10項目以内。増やすより分割する

## タグの語彙（要約タスクはこの中からしか選べない）
`http-input`, `db`, `shell`, `filesystem`, `template`, `deserialize`, `xml`, `outbound-http`,
`auth`, `session`, `crypto`, `config`, `secrets`, `ci`, `container`, `iac`, `llm`, `memory-unsafe`, `regex`

語彙を増やすときは `scripts/va.py` の `TAGS` も更新する（`va-guard` CI が整合性を検査する）。
