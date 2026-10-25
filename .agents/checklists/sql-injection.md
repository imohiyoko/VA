---
id: sql-injection
tags: [db]
langs: [any]
categories: [sqli, nosqli]
---
- クエリ文字列を `+`・f-string・テンプレートリテラル・`format`・`%` で組み立て、その中に外部入力が入るか
  - 危険: `"SELECT * FROM u WHERE id=" + req.id` / 安全: プレースホルダ `?`, `$1`, `:id` に値を渡す
- ORM の raw 系 API（`raw()`, `execute()`, `$queryRawUnsafe`, `whereRaw`, `Sequelize.literal`）に外部入力が入るか
- ORDER BY・カラム名・テーブル名を外部入力から作っているか（プレースホルダが使えない箇所。許可リストがあれば安全）
- NoSQL: リクエストのオブジェクトをそのままクエリに渡していないか（`{ $ne: null }` 等の演算子注入）
- 入力が「数値に変換済み」「許可リストで検証済み」なら候補にしない
