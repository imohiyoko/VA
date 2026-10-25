# 段階: 報告

`python3 scripts/va.py report --run <run>` がすべて生成する。LLM は関与しない。

## run ディレクトリ `operator/targets/<target>/runs/<YYYYMMDD>-<sha7>/`

| ファイル | 内容 |
|---|---|
| `meta.json` | 対象コミット、VA バージョン、モデル、モード、ツールの状態、件数、コスト |
| `queue.json` | 各段階のタスク（再開可能。途中で止まっても `exec` を再実行すれば続きから） |
| `results/*.json` | 各 LLM タスクの検証済み出力（`_meta` にモデル・試行回数・コスト） |
| `failures/*.json` | 2回失敗したタスク |
| `candidates.json` | トリアージ前の候補（fingerprint 付き） |
| `findings.json` | 確定結果 |
| `report.md` | 人が読むレポート |
| `changes.md` | 前回からの変更の概略 |

## findings.json の項目

`fingerprint`, `category`, `title`, `severity`, `status`, `confidence`, `location{path,line}`, `attacker`,
`evidence`, `rationale`, `fix`, `source`(llm/semgrep/gitleaks/osv-scanner), `fp_reason`, `first_seen`,
`triage_model`, `carried_over`(diff モードで再確認していない継続分)

## fingerprint

`sha256(category + ":" + path + ":" + 空白を除いた該当行)` の先頭16桁。行番号を含めないので、行がずれても同じ ID になる。
該当行が変わると ID も変わる（＝コードが変わったので再評価する）。

## 新規・継続・解消

- 新規: 前回の findings に無い
- 継続: 前回にもある。diff モードで今回レビューしなかったファイルのものは `carried_over` として引き継ぐ
- 解消: 前回あって今回無く、かつそのファイルを今回レビューした（またはファイルが消えた、ツール由来の指摘）

## 人による判定（state.json）

`operator/targets/<target>/state.json` の `suppressed` に `{"<fingerprint>": "false_positive|accepted_risk|wont_fix|fixed"}` を書くと、
次回から再報告されない。誤検知の理由は `learnings.md` に1行書いておくと retrospective が学習に使う。
