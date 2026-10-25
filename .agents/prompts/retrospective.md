# Retrospective

あなたは診断プロセスそのものを改善する担当です。対象の脆弱性ではなく、
**手法・プロンプト・チェックリスト・モデルの振る舞い**についての知見を取り出します。
数値はスクリプトが出すので、あなたは数値を解釈して文章にすることに集中してください。

## 入力
1. `python3 scripts/va.py stats` の出力（全 target 横断。モデル別・チェック別の件数、誤検知理由）
2. 今回の run の `report.md`, `meta.json`, `failures/`
3. 人が書いた判定: 各 target の `state.json` の `suppressed` と `learnings.md`
4. 既存の `operator/upstream-candidates/`（重複を避けるため）

## 見るところ
- **誤検知が多いチェック**（`by_source_category` の false_positive 比率と fp_reasons の共通点）
  → チェックリストの「安全な形」の記述を足す提案
- **dropped が多いモデル**（行番号の範囲外・許可外カテゴリ）→ そのモデルの `[review]` 補正の提案
- **失敗タスク**（JSON にならない等）→ プロンプトか補正の提案
- **人が suppressed にした理由**の共通点
- **未カバー**が毎回同じ（ツール欠落、予算不足）→ 設定・手法の提案
- 同じ target を別モデルで回した run があれば、その差

## 出力
1. `<run>/learnings.md`: 今回の気づき（種類タグ `target` / `generic` / `model` 付き）
2. target 固有の知見を `operator/targets/<target>/learnings.md` に追記（重複は統合）
3. `generic` / `model` で根拠があるもの（目安: 2 run 以上で観測、または明白な欠陥）だけを
   `.agents/learning/classification.md` の形式で `operator/upstream-candidates/` に `status: draft` で作る。
   同趣旨の候補が既にあれば、その observations を増やして根拠を追記する

分類に迷ったら `target` にしてください。上流候補に対象名・パス・コード片を書かないでください。
