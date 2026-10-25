# VA — Vulnerability Assessment kit for coding agents

リポジトリを定期的に脆弱性診断するための**共通基盤**です。
**Haiku クラスの軽量モデルでも動き、CI で回せること**を目標にしています。

- 判断が必要な小さな仕事（1ファイルの要約・1ファイル×チェックリストのレビュー・候補1件の検証）だけを LLM に渡す
- それ以外（ファイル列挙、差分検出、キャッシュ、静的解析ツール、JSON 検証、重複排除、前回との比較、レポート）は
  `scripts/va.py`（Python 標準ライブラリのみ）が決定的に行う

```
VA (public, 共通基盤)  ──upstream──▶  運用リポジトリ (private, 例: VA_imohiyoko)
        ▲                                   │ 定期診断 → target ごとの索引・結果・学習
        └──── 汎用的な改善を PR（サニタイズ済み）┘
```

## 構成

| パス | 役割 |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | エージェント共通の指示 / Claude Code 用入口（`@AGENTS.md`） |
| `.agents/methodology/` | 手法の説明（パイプライン、索引、トリアージ基準、報告形式） |
| `.agents/checklists/` | レビュー観点（単一の情報源。ファイルのタグで自動選択） |
| `.agents/prompts/tasks/` | 軽量モデル向けタスクプロンプト（summarize / review / triage） |
| `.agents/prompts/` | retrospective・upstream-proposer のプロンプト |
| `.agents/model-profiles/` | モデルごとの傾向と補正（`- [review] ...` の行がプロンプトに自動注入される） |
| `.agents/learning/` | 学習の分類ルール、上流提案ポリシー |
| `.agents/VERSION`, `CHANGELOG.md` | 手法のバージョン（全 run に記録される） |
| `.claude/agents/`, `.claude/skills/` | Claude Code の入口（`/va-audit`, `/va-sync-upstream`, `/va-propose-upstream`） |
| `scripts/va.py` | パイプライン本体 |
| `scripts/*.sh` | 運用リポジトリの初期化・同期・上流提案のサニタイズ |
| `templates/operator/` | 運用リポジトリの雛形（設定、GitHub Actions） |
| `operator/` | **運用データ**。VA では `.gitignore` で除外、運用リポジトリでだけ追跡 |

Claude Code は現時点で `.agents/` ディレクトリを自動では読みません（`AGENTS.md` は読みます）。
本体を `.agents/` に置き、`.claude/` の入口から参照する構成にしています。

## 使い始める

```bash
# 空の private リポジトリを clone したルートで
git clone https://github.com/imohiyoko/VA.git /tmp/VA && /tmp/VA/scripts/bootstrap-operator.sh
# operator/va.toml に target を追加し、Secrets を設定して push
```

手順の詳細: [docs/operator-guide.md](docs/operator-guide.md) / 設計: [docs/architecture.md](docs/architecture.md) /
上流への貢献: [docs/contributing-upstream.md](docs/contributing-upstream.md)

## 1回の診断

```bash
RUN=$(python3 scripts/va.py plan --target owner/repo --src work/target)   # 列挙・差分・ツール
python3 scripts/va.py exec --run "$RUN"                                     # LLM タスク（claude -p / API）
python3 scripts/va.py report --run "$RUN"                                   # findings・report.md・changes.md
python3 scripts/va.py stats                                                 # モデル別・チェック別の集計
```

## 注意

- この基盤は public です。**診断結果・対象リポジトリ名・コード断片はここへ入れないでください。**
  `.gitignore`、提案時の sanitize チェック、CI（`va-guard`）で防いでいます。
- 診断対象のコードは信頼できない入力として扱い、実行しません（`AGENTS.md`）。

## ライセンス

[Apache License 2.0](LICENSE)
