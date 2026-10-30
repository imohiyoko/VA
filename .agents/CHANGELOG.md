# Changelog

`.agents/VERSION` の変更履歴。SemVer の意味は次のとおり。

- **MAJOR**: finding の形式・fingerprint の算出方法・ディレクトリ構成が変わり、過去の run と直接比較できなくなる変更
- **MINOR**: チェック項目・手法・プロンプトの追加や挙動の変化（検出結果が変わりうる）
- **PATCH**: 誤字・説明の明確化など、検出結果に影響しない変更

上流 PR では必ずこのファイルに1行追記し、`VERSION` を上げる。

## 0.2.0 — 2026-10-30

- `osv-scanner` を `--no-ignore` で実行する。対象の clone が運用リポジトリの `work/`（.gitignore 対象）にあると
  lockfile がすべて無視され、毎回 `failed` になっていた。依存の検出結果が変わるので MINOR（次の run はフルスキャン）。
- `va.py detect` を追加: target ごとにリモートの HEAD（`ref` があればそのブランチ）と前回診断したコミットを比べ、
  audit（first・changed・va-upgraded・retry）/ skip（same・empty・unreachable）を出す。
  HEAD が同じでも、VA の MINOR 以上が上がった target と、前回の run に失敗タスクがあった target（同じコミットで 1 回だけ）は audit にする。
- 運用テンプレートに `operator/routine.md`（エージェントのスケジュール実行用。結果は `va-data` ブランチに直接記録）を追加。

## 0.1.1 — 2026-10-27

- サニタイズの強化: denylist が読めなければ失敗、`+` で始まる追加行・コミットメッセージ・PR 本文も検査。
  提案の push はエージェントが触っていない clone から行う。`va-guard` の運用リポジトリ判定を PR の base で行う。

## 0.1.0 — 2026-10-25

- 初版。決定的パイプライン `scripts/va.py`（plan / summarize / review / triage / report）と軽量モデル向けタスクプロンプト、
  タグで選ぶチェックリスト 17 種、blob SHA による要約キャッシュ、retrospective / upstream-proposer、
  モデルプロファイルの雛形、運用リポジトリ用テンプレート、`va-guard` CI。
