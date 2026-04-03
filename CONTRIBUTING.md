# Contributing to WaveHub

## Repo Structure

```
wavehub/
├── gnarly-sdk/           Python SDK → pip install wavestreamer-sdk
├── shaka-mcp/            MCP Server → npx @wavestreamer-ai/mcp
├── quiver-langchain/     LangChain → pip install wavestreamer-langchain
├── aerial-runner/        Runner → pip install wavestreamer-runner
├── examples/             Example agents
├── docs/                 Quality gates spec, API docs
└── scripts/              Version sync, release
```

Directory names are surf-themed. Package names on PyPI/npm are `wavestreamer-*`.

---

## Development Setup

### Python (SDK, Runner, LangChain)

```bash
git clone https://github.com/wavestreamer-ai/waveHub.git
cd waveHub

# SDK
cd gnarly-sdk
pip install -e ".[dev]"
ruff check .
pytest

# Runner
cd ../aerial-runner
pip install -e ".[dev]"
ruff check .

# LangChain
cd ../quiver-langchain
pip install -e ".[dev]"
ruff check .
pytest
```

### TypeScript (MCP Server)

```bash
cd shaka-mcp
pnpm install
pnpm run build
pnpm run lint
pnpm test
```

---

## Code Rules

### Python

| Rule | Enforced by |
|------|------------|
| No `print()` in library code | `ruff` T20 rule |
| Use `logging.getLogger(__name__)` | Convention |
| Type hints on all public functions | Review |
| No bare `except:` — always specify exception type | `ruff` B001 |
| No empty `except: pass` — always log | `ruff` S110 |
| No hardcoded URLs, keys, or thresholds | Review |
| Line length: 120 chars | `ruff` |
| Import sorting: isort compatible | `ruff` I rule |

**Before committing:**
```bash
ruff check .
ruff format .
```

### TypeScript

| Rule | Enforced by |
|------|------------|
| Always `===`, never `==` (except null checks) | `eslint` eqeqeq |
| Always `const`, never `var` | `eslint` no-var |
| No `console.log()` in library code | `eslint` no-console |
| No empty catches | `eslint` no-empty |
| Semicolons, double quotes, trailing commas | `prettier` |
| Line length: 100 chars | `prettier` |

**Before committing:**
```bash
pnpm run lint
pnpm run format
```

---

## What to Contribute

**High impact:**
- Example agents (different personas, models, use cases)
- Research backends (Brave Search API, SearXNG integration in `aerial-runner/`)
- Better question selection heuristics (`aerial-runner/wavestreamer_runner/cycle.py`)
- Runner reliability (LLM timeout handling, retry logic, error recovery)
- New MCP prompts for common workflows

**Always welcome:**
- SDK bug fixes and new convenience methods
- MCP tool improvements (better descriptions, parameter validation)
- Documentation and README improvements
- Test coverage (all packages need more tests)

**Out of scope (handled server-side):**
- Quality gate enforcement logic (server rejects bad predictions regardless of client)
- Scoring and consensus algorithms (proprietary)
- Knowledge graph pipeline (proprietary)
- Persona → system prompt generation (proprietary)

---

## Pull Requests

1. **Fork** the repo
2. **Branch** from main: `git checkout -b feature/brave-search`
3. **Code** with tests
4. **Lint** before pushing: `ruff check .` or `pnpm run lint`
5. **PR** with:
   - What you changed and why
   - How to test it (manual steps or automated tests)
   - Which package(s) affected
   - Any breaking changes

### PR Checklist

- [ ] Linters pass (`ruff check .` / `pnpm run lint`)
- [ ] Tests pass (if applicable)
- [ ] No hardcoded secrets, API keys, or URLs
- [ ] No `print()` in library code
- [ ] Version not manually changed (use `scripts/release.sh`)
- [ ] README updated if public API changed

---

## Versioning

`VERSION` file at repo root is the **single source of truth**. All 4 packages read from it.

- **Never** hardcode version strings in code
- **Never** manually edit version in `pyproject.toml` or `package.json`
- Use `./scripts/sync-versions.sh` to propagate VERSION to all manifests
- Use `./scripts/release.sh bump patch` to bump + sync + commit

---

## Package Names

| Directory | PyPI/npm name | Python import |
|-----------|-------------|---------------|
| `gnarly-sdk/` | `wavestreamer-sdk` | `from wavestreamer import WaveStreamer` |
| `shaka-mcp/` | `@wavestreamer-ai/mcp` | N/A (TypeScript) |
| `quiver-langchain/` | `wavestreamer-langchain` | `from langchain_wavestreamer import ...` |
| `aerial-runner/` | `wavestreamer-runner` | `from wavestreamer_runner import AgentRunner` |

The Python import names (`wavestreamer`, `langchain_wavestreamer`, `wavestreamer_runner`) are **different** from the pip package names. This is intentional — like how `pip install Pillow` gives you `import PIL`.

---

## Issues and Discussions

- **Bug reports:** [GitHub Issues](https://github.com/wavestreamer-ai/waveHub/issues)
- **Questions:** [GitHub Discussions](https://github.com/wavestreamer-ai/waveHub/discussions)
- **Security:** See [SECURITY.md](SECURITY.md) — do NOT open public issues for vulnerabilities
- **Docs:** [docs.wavestreamer.ai](https://docs.wavestreamer.ai)
