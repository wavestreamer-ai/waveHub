# Copilot Instructions for WaveHub

Follow this rule priority:

1. `../CODE_STANDARDS.md` (canonical standard in monorepo)
2. `../AI_RULES.md` (rule hierarchy + workflow skills)
3. `../AGENTS.md` (agent/tool read order)
4. `../wavehub/.cursorrules` (repo-local addendum)

If guidance conflicts, follow the higher-priority source.

## Required Workflow

- Add tests for new features.
- Add regression tests for bug fixes.
- Never swallow errors silently.
- Never duplicate shared source-of-truth logic.
- Run package-local checks before finalizing changes:
  - Python packages: `ruff check . && ruff format --check . && mypy . && pytest`
  - TypeScript package (`shaka-mcp`): `pnpm lint && pnpm format:check && pnpm test`

## Repo-specific Addendum

- Keep SDK/API changes backward compatible unless intentionally versioned.
- Do not hardcode versions; use root `VERSION` and sync scripts.
