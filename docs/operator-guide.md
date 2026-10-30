# 運用ガイド

## 1. 運用リポジトリを作る

1. GitHub に **private** の空リポジトリを作る（README だけあってもよい）
2. clone して、そのルートで:
   ```bash
   git clone https://github.com/imohiyoko/VA.git /tmp/VA
   /tmp/VA/scripts/bootstrap-operator.sh
   ```
   - 別の VA（フォーク等）を使う場合は URL を引数で渡す: `bootstrap-operator.sh https://github.com/<org>/VA.git`
3. `operator/va.toml` に `[[targets]]` を追加、`operator/sanitize-denylist.txt` に対象名・社内用語を書く
4. `git push`

## 2. GitHub の設定

**Secrets**（Settings → Secrets and variables → Actions）

| 名前 | 用途 | 権限 |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` または `ANTHROPIC_API_KEY` | モデル呼び出し | — |
| `VA_TARGETS_TOKEN` | 診断対象の読み取り | 対象リポジトリの Contents: Read-only（fine-grained PAT） |
| `VA_UPSTREAM_TOKEN` | VA への提案 PR | VA の Contents: Read and write, Pull requests: Read and write |

**Variables**（任意）: `VA_UPSTREAM_URL`, `VA_UPSTREAM_REPO` — VA 以外を upstream にする場合

**Settings → Actions → General**: 「Allow GitHub Actions to create and approve pull requests」を有効化

## 3. ワークフロー

| ワークフロー | いつ | 何をする |
|---|---|---|
| `va-audit` | 毎週月曜 / 手動（target・mode 指定可） | target ごとに診断し、結果を PR にする |
| `va-sync-upstream` | 毎週日曜 / 手動 | VA の更新を取り込む PR を作る |
| `va-propose-upstream` | `operator/upstream-candidates/` が main に入ったとき / 手動 | `status: ready` の候補を VA への PR にする |

### エージェントのスケジュール実行で回す

Actions の API キーを使わず、Claude Code などのスケジュール実行で回すこともできる。手順は `operator/routine.md`（雛形あり）。

- 差分判定は `python3 scripts/va.py detect`（リモートの HEAD と `state.json` の `last_commit` を比較。`--changed` で診断対象だけを出す）。
  HEAD が同じでも、VA の MINOR 以上が上がったとき（`va-upgraded`）と、前回の run に失敗したタスクか静的解析ツールがあったとき（`retry`、同じコミットで 1 回だけ）は診断対象になる
- 結果は PR にせず **`va-data` ブランチに直接 commit** する。診断 PR がマージされずに残ると main の `state.json` が古くなり、
  次回の差分判定が古い状態と比べてしまうため。最新の結果は `va-data` を見る
- 誤検知などの判定（`suppressed`）は `va-data` 上の `state.json` に書く

## 4. 日々の運用

1. **診断 PR が来たら** `report.md`（PR 本文）を読む
   - 誤検知: `state.json` の `suppressed` に `"<fingerprint>": "false_positive"` を追加し、理由を `learnings.md` に1行
   - 受容: `accepted_risk` / 対応しない: `wont_fix` / 修正済み: `fixed`
2. **retrospective が作った上流候補**（`operator/upstream-candidates/*.md`, `status: draft`）を読み、
   出してよければ `status: ready` にしてマージ → VA に PR が出る
3. **VA で PR をマージ** → 次の同期 PR で各運用リポジトリに入る

## 5. ローカル・対話で使う

```bash
git clone --filter=blob:none https://github.com/<owner>/<repo> work/target
python3 scripts/va.py detect                        # 前回の診断から変更があるか
RUN=$(python3 scripts/va.py plan --target <owner>/<repo> --src work/target)
python3 scripts/va.py exec --run "$RUN"            # runner は operator/va.toml
python3 scripts/va.py report --run "$RUN"
```

Claude Code では `/va-audit <owner/repo>`。`exec` の runner が使えない環境では、
セッション自身が `next` / `submit` でタスクをこなす（その場合も1タスクずつ独立に扱う）。

## 6. モデルを変える・比べる

- `operator/va.toml` の `model`（全体）または `[[targets]]` の `model`（個別）
- 重大度が高い候補だけ上位モデルでトリアージ: `escalate_model = "claude-sonnet-5-5"`
- 比較したいときは同じ target を `workflow_dispatch` で `mode: full` にして別モデルで回し、`va.py stats` で比べる

## 7. コストの目安を見る

各 `meta.json` の `usage`（タスク数・再利用数・失敗数・コスト）と `report.md` 冒頭の1行。
初回はフルスキャン（全ファイル要約）なので高く、2回目以降は変更分＋ローテーション分だけになる。
