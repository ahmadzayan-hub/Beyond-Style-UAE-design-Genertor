# Claude Code Low-Token Operating Guide

## Core rule
Keep root `CLAUDE.md` small and persistent. Keep the large product spec in `docs/BEYOND_STYLE_MASTER_SPEC.md`. Read only the needed section.

## Session commands
Use when supported by the installed Claude Code version:
- `/clear` — start unrelated task with clean context.
- `/context` — inspect context usage.
- `/compact focus on current task, decisions, changed files, failing tests, blockers and next action; omit discarded exploration and verbose logs`
- `/cost` — inspect usage.
- `/model` — choose the lightest capable model.
- `/model opusplan` — planning/execution split if available.
- `/btw` — side question without polluting main work if available.
- `/help` — confirm commands.

## Low-token prompts

### Audit
`Read CLAUDE.md. Audit only files relevant to P0 Golden Path. Do not code. Return existing/reusable/gaps/risks + max 12-file plan. Do not restate spec.`

### Implement
`Read CLAUDE.md. Implement only <SLICE>. Inspect minimum files. Preserve working code. Run targeted tests. Update docs/production-readiness.md. Reply <=10 lines.`

### Fix
`Fix only <BUG>. Use targeted search. No unrelated refactor. Add regression test. Reply changed files + test result only.`

### Continue
`Continue current P0 slice. Read git diff + production-readiness.md first. Do not re-read unchanged files. Complete smallest missing step and test.`

### Review
`Review only current diff against CLAUDE.md. Report P0 blockers first. Do not rewrite unless blocker is confirmed.`

### Checkpoint
`Write durable decisions/evidence to production-readiness.md or ADR, then compact current P0 slice only.`

## Cost-control rules
1. Use `rg` before opening files.
2. Read relevant functions/ranges, not full large files.
3. Do not re-read unchanged files.
4. Before editing >3 files, list planned files/reasons once.
5. Use targeted tests while iterating; full suites only at phase gates.
6. Summarize logs; show only failure evidence.
7. Never restate CLAUDE.md/spec in chat.
8. Keep task responses <=10 lines unless asked for analysis.
9. Stay inside P0 until acceptance passes.
10. Feature-flag expensive/experimental functionality.
