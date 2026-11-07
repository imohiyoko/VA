# Changelog

`.agents/VERSION` の変更履歴。SemVer の意味は次のとおり。

- **MAJOR**: finding の形式・fingerprint の算出方法・ディレクトリ構成が変わり、過去の run と直接比較できなくなる変更
- **MINOR**: チェック項目・手法・プロンプトの追加や挙動の変化（検出結果が変わりうる）
- **PATCH**: 誤字・説明の明確化など、検出結果に影響しない変更

上流 PR では必ずこのファイルに1行追記し、`VERSION` を上げる。

## 0.4.0 — 2026-11-07

- 「権限昇格」の観点を追加（`methodology/09-privilege-escalation.md`）。限られた管理権限（ロールの管理など）を持つ主体が、
  持たない権限を入れたロールを作って自分に付与できる、という型の脆弱性を見つける。
  - チェックリスト `privilege-escalation`（`tags: [auth]`）: 付与する権限 ⊆ 呼び出し主体の権限の確かめ、全経路、ワイルドカード、
    自分への付与、denylist で特権を判定する作り、定義と別の場所にある手書きの一覧、名前空間の衝突、付与の範囲
  - パス名がロール・権限らしいファイル（`PRIV_HINT`）は要約に関係なく `auth` タグを足し、risk を 2 以上にする
  - 新しい段階 crosscheck（review と triage の間）: スクリプトが権限らしいリテラル `"<resource>:<action>"`（`perm_pattern` で変更可）の
    定義の集合と、それを並べた一覧の候補を決定的に抜き出し、漏れのある一覧 1 つずつを軽量モデルが判定する
    （`prompts/tasks/check-list-gap.md`）。`decides_access` かつ `missing` ありで `authz-list-gap` の候補になり、通常どおり triage する。
    同じ一覧・同じ漏れ・同じ使われ方は前回の判定を再利用、1 run の上限は `crosscheck_budget`（既定 30）。漏れが 80 件を超える一覧は
    分けて全件判定し、1 件にまとめる。fingerprint に漏れた項目を含める。一覧の使われ方を triage にも渡す
    一覧の境界は、複数行の一覧の開始行と 1 行の一覧（`NAME = [...]`、`x := []string{...}`）で分ける。`validate` が境界の回帰を確かめる
  - triage に `authz-list-gap` / `privilege-escalation` の判定基準（一覧・確かめが付与の判断に使われ、緩い側に倒れるか）を追加
  - `report.md` に「Privilege-escalation check」節（ゼロ件でも出す）と Summary の件数、該当 finding に手での再現手順の雛形
    （付与の前に 403、付与の後に 200。VA は対象を実行しない）を追加
- 検出結果が変わるので MINOR（次の run はフルスキャン）。

## 0.3.0 — 2026-11-06

- 「悪意の有無」の観点を追加。脆弱性（外の攻撃者が悪用できるか）とは別に、コード自身（作者・依存・CI）が
  利用者を裏切っていないかを見る（`methodology/08-malicious-intent.md`）。
  - チェックリスト `malicious-code`（常に適用）: backdoor / data-exfiltration / credential-harvesting / obfuscated-payload /
    malicious-install-hook / suspicious-ci / malicious-dependency / destructive-payload
  - 要約に `malice_suspect` を追加（立てば risk 3）。この項目を持たない古い索引は 1 回だけ要約し直す
  - インストール・ビルド・コミット時に動くファイルと依存の宣言を強制レビュー（risk 2 以上）。`go.mod`、`requirements.txt`、
    `Gemfile`、`.npmrc`、拡張子のない git フックを索引に入れる
  - diff モードでは変更ファイルを risk 0 でもすべてレビューする
  - osv-scanner の `MAL-` advisory を `malicious-dependency`（critical、likely）にする
  - attacker に `code-author` を追加。レビュー・トリアージのプロンプトに悪意の観点の判定基準を追加
  - `report.md` に「Malicious-intent check」節（ゼロ件でも出す）と Summary の件数を追加
- 検出結果が変わるので MINOR（次の run はフルスキャン）。

## 0.2.0 — 2026-10-30

- `osv-scanner` を `--no-ignore` で実行する。対象の clone が運用リポジトリの `work/`（.gitignore 対象）にあると
  lockfile がすべて無視され、毎回 `failed` になっていた。依存の検出結果が変わるので MINOR（次の run はフルスキャン）。
- `va.py detect` を追加: target ごとにリモートの HEAD（`ref` があればそのブランチ）と前回診断したコミットを比べ、
  audit（first・changed・va-upgraded・retry）/ skip（same・empty・unreachable）を出す。
  HEAD が同じでも、VA の MINOR 以上が上がった target と、前回の run に失敗したタスクか静的解析ツールがあった target（同じコミットで 1 回だけ）は audit にする。
- 静的解析ツールの出力ファイルを実行前に消す（ツールが出力しなかったとき、前回の結果を今回の結果として読まないように）。
- 運用テンプレートに `operator/routine.md`（エージェントのスケジュール実行用。結果は `va-data` ブランチに直接記録）を追加。

## 0.1.1 — 2026-10-27

- サニタイズの強化: denylist が読めなければ失敗、`+` で始まる追加行・コミットメッセージ・PR 本文も検査。
  提案の push はエージェントが触っていない clone から行う。`va-guard` の運用リポジトリ判定を PR の base で行う。

## 0.1.0 — 2026-10-25

- 初版。決定的パイプライン `scripts/va.py`（plan / summarize / review / triage / report）と軽量モデル向けタスクプロンプト、
  タグで選ぶチェックリスト 17 種、blob SHA による要約キャッシュ、retrospective / upstream-proposer、
  モデルプロファイルの雛形、運用リポジトリ用テンプレート、`va-guard` CI。
