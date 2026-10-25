# claude-haiku-5-5

## 補正

`- [summarize] ...` / `- [review] ...` / `- [triage] ...` / `- [all] ...` で始まる行は、
`scripts/va.py` がそのタスクのプロンプト末尾に自動で追加する（英語で、1行1ルール、命令形で書く）。
根拠は次の行にインデントして残す（こちらはプロンプトには入らない）。

<!-- 例:
- [triage] For dep-vuln or hardcoded-secret in test files, use severity low at most.
  - 根拠: 誤検知 12/15 件, 6 runs, 3 targets / VA 0.1.x, 2026-11
-->

## 観測された傾向（補正にまだしていないもの）

## 統計（retrospective が `va.py stats` から更新）

| 期間 | runs | triage 件数 | false_positive | review の dropped |
|---|---|---|---|---|
