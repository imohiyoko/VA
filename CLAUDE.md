@AGENTS.md

## Claude Code 固有

- 診断の起点はスキル `/va-audit <owner/repo>`。上流同期は `/va-sync-upstream`、上流提案は `/va-propose-upstream`。
- サブエージェント（`.claude/agents/`）は入口だけで、本体プロンプトは `.agents/prompts/` にある。必ず本体を読んでから動く。
- `operator/overrides.md` が存在すれば最初に読む。
