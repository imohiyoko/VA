# 設計

## 目標

1. **軽量モデル（Haiku クラス）で動く** — 判断の単位を小さくし、残りは決定的なスクリプトで行う
2. **CI で定期的に回せる** — 対話不要、再開可能、コストが読める
3. **改善が還流する** — 運用で得た汎用的な学びを、安全に共通基盤へ戻す
4. **結果が比較できる** — 手法バージョン・モデル・対象コミットを全 run に記録する

## 二つのリポジトリ

| | VA（upstream） | 運用リポジトリ（例: VA_imohiyoko） |
|---|---|---|
| 公開範囲 | public | private |
| 中身 | 手法、プロンプト、チェックリスト、モデルプロファイル、スクリプト、雛形 | VA 一式 ＋ `operator/`（設定・索引・結果・学習） |
| 変更方法 | PR（運用リポジトリからの提案、または直接） | `operator/` のみ直接編集。共通層は upstream から同期 |
| 守り | `.gitignore` で `operator/` を除外 ＋ `va-guard` CI ＋ 提案時の sanitize チェック | — |

運用リポジトリは VA を `upstream` リモートとして履歴ごとマージしている。
同じアカウント内ではフォークできないため。別アカウント・別 org ではフォークでもよい。

`.gitignore` の `va:operator-data` ブロックは、運用リポジトリでは `scripts/va-operator-gitignore.sh` が取り除く
（同期スクリプトが毎回適用するので、上流で `.gitignore` が変わっても運用データは追跡され続ける）。

## `.agents/` と `.claude/`

Claude Code は `AGENTS.md` を読むが、`.agents/` ディレクトリは読まない（2026-10 時点の公式ドキュメント）。
そのため次のように分けている。

- `.agents/` — 本体（ツール非依存）。手法・タスクプロンプト・チェックリスト・モデルプロファイル・学習ルール
- `.claude/agents/`, `.claude/skills/` — Claude Code の入口。本体を読むよう指示するだけの薄い定義
- `AGENTS.md` — 共通指示。`CLAUDE.md` は `@AGENTS.md` で読み込む

他のエージェントツールを使う場合や、Claude Code が `.agents/` を直接読むようになった場合は、入口だけを差し替えればよい。

## データの流れ

```
            ┌──────────── 運用リポジトリ (private) ─────────────────────────────────┐
 target ──▶ │ plan ─▶ summarize ─▶ review ─▶ triage ─▶ report ─▶ retrospective     │
 (read)     │  (script)  (LLM)      (LLM)     (LLM)    (script)     (LLM)          │
            │                                                     │               │
            │  operator/targets/<t>/index/files.jsonl  ◀──────────┤               │
            │  operator/targets/<t>/runs/<run>/…        ◀─────────┘               │
            │  operator/upstream-candidates/*.md  ◀── generic / model learnings    │
            └───────────────────────────────┬────────────────────────────────────┘
                     人がレビュー(status: ready) │ sanitize check → PR
                                            ▼
                                     VA (public) ──▶ sync ──▶ 各運用リポジトリ
```

## 状態の置き場所

| データ | 場所 | 形式 | 理由 |
|---|---|---|---|
| ファイル要約（索引） | `operator/targets/<t>/index/files.jsonl` | JSONL、パス順 | 1行差分で読める、blob SHA でキャッシュ |
| 変更の概略 | `runs/<run>/changes.md` | Markdown（生成） | 人が読む |
| 結果 | `runs/<run>/findings.json`, `report.md` | JSON / Markdown | 比較・人が読む |
| 人の判定 | `operator/targets/<t>/state.json` の `suppressed` | JSON | 再報告の抑制 |
| 学習 | `operator/targets/<t>/learnings.md`, `operator/upstream-candidates/` | Markdown | 人がレビューする |
| 集計 | `va.py stats`（都度計算） | JSON | 保存しない＝ずれない |

DB は使わない。git が履歴とレビュー（PR）を提供し、CI からそのまま読み書きできるため。
集計クエリが重くなったら、CI 上で JSONL から SQLite を都度生成する（コミットしない）。

## 脅威と対策

| 脅威 | 対策 |
|---|---|
| 対象コード内のプロンプトインジェクション | 各タスクは独立プロセス・空ディレクトリ・ツールなしで実行。出力はスキーマ検証。AI 向けの文は `injection_suspect` として最優先でレビューしレポートに列挙 |
| 細工された要約で重要ファイルを隠す | 要約は優先度付けにのみ使用。パス名ヒューリスティック・kind で強制レビュー |
| 対象コードの実行 | 実行しない（静的解析ツールのみ）。CI では対象を `persist-credentials: false` で checkout、retrospective 前に削除 |
| public への情報漏洩 | `.gitignore`、提案ブランチの push はスクリプトのみ（sanitize 必須）、非公開 denylist、`va-guard` CI |
| トークンの露出 | 上流トークンは LLM ステップに渡さない。対象トークンは read-only の fine-grained PAT |
