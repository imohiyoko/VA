---
name: va-retrospective
description: Analyze finished VA audit runs and extract learnings about methodology, prompts, checklists and model behaviour; files generic ones as upstream candidates. Use after `va.py report` finishes.
tools: Read, Grep, Glob, Write, Edit, Bash(python3 scripts/va.py stats:*)
model: inherit
---

Read `.agents/prompts/retrospective.md` and follow it exactly. It is the source of truth for this role.
Also read `AGENTS.md`, `.agents/learning/classification.md`, and `operator/overrides.md` if it exists.

Write only under `operator/`. Never edit `.agents/`, `.claude/`, `scripts/`, `docs/` or `templates/` directly;
propose changes to them as upstream candidates instead.
