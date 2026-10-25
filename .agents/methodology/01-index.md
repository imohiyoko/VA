# 段階1: ファイル索引（要約キャッシュ）

## 置き場所と形式

`operator/targets/<target>/index/files.jsonl` — 1ファイル1行、パス順。git で差分が読める。

```json
{"path": "src/api/users.ts", "blob": "<git blob sha>", "lang": "typescript", "lines": 182,
 "purpose": "...", "kind": "entry", "tags": ["http-input", "db", "auth"],
 "entry_points": ["GET /users/:id"], "sinks": ["knex.raw in updateUser"], "risk": 3,
 "injection_suspect": false, "model": "claude-haiku-5-5", "va_version": "0.1.0",
 "updated": "<run id>", "reviewed_at": "<run id>"}
```

- **キー**は `path` と `blob`。blob が前回と同じなら要約し直さない
- `reviewed_at` はレビュー段階を最後に通った run。diff モードのローテーションで、古いものから順に再レビューする
- `model` / `va_version` で「どのモデル・どの手法で作られた要約か」が分かる。
  要約タスクのプロンプトを大きく変えた場合は MINOR を上げる（フルスキャンが走り、変更ファイル以外は再利用される点に注意。
  全件作り直したいときは `index/files.jsonl` を削除する）

## なぜ DB でもコード内コメントでもないか

- **SQLite 等の DB**: バイナリなので git で差分・マージができず、履歴も追いにくい。必要なら CI 上で JSONL から都度生成する派生物にする
- **対象コード内**: 対象リポジトリへの書き込みが必要になり、また攻撃者がコード内の要約を書き換えられる
- **JSONL in 運用リポジトリ**: 差分が1行単位で読め、git が履歴を持ち、CI からそのまま読み書きできる

## 変更の概略

run ごとに `runs/<run>/changes.md` をスクリプトが生成する（前回コミットからの diff 統計と、変更ファイルの新しい要約）。
