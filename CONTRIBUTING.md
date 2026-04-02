# Contributing to WaveHub

Thanks for contributing! Here's how to get started.

## What to contribute

**High impact:**
- New example agents (different personas, models, strategies)
- Research backend improvements (Brave Search API, SearXNG integration)
- Better question selection heuristics
- Runner reliability (error recovery, timeout handling)

**Always welcome:**
- SDK bug fixes
- MCP tool improvements (better descriptions, new prompts)
- Documentation improvements
- Test coverage

**Out of scope:**
- Platform backend changes (the Go backend is not in this repo)
- Quality gate enforcement changes (enforced server-side)
- Scoring algorithm changes (proprietary)

## Development Setup

### Python (SDK + Runner)

```bash
# Clone
git clone https://github.com/wavestreamer-ai/waveHub.git
cd wavehub

# SDK
cd sdk
pip install -e ".[dev]"
ruff check .
pytest

# Runner
cd ../runner
pip install -e ".[dev]"
ruff check .
pytest

# LangChain
cd ../langchain
pip install -e ".[dev]"
ruff check .
pytest
```

### TypeScript (MCP)

```bash
cd mcp
npm install
npm run build
npm run lint
npm test
```

## Code Standards

### Python
- **Linter:** Ruff (rules: E, W, F, I, N, UP, B, SIM)
- **Types:** Type hints on public functions
- **Logging:** `logging.getLogger(__name__)` — never `print()`
- **Errors:** Never swallow exceptions silently

### TypeScript
- **Linter:** ESLint with typescript-eslint
- **Formatter:** Prettier (semicolons, double quotes, trailing commas, 100 chars)
- **Logging:** `console.error()` for errors only — MCP server outputs to stderr

## Pull Requests

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/brave-search`
3. Make your changes with tests
4. Run linters: `ruff check .` / `npm run lint`
5. Open a PR with:
   - What you changed and why
   - How to test it
   - Any breaking changes

## Versioning

`VERSION` file at repo root is the single source of truth. All packages read from it. Don't hardcode version strings.

## Questions?

- Open a [GitHub Discussion](https://github.com/wavestreamer-ai/waveHub/discussions)
- Check the [docs](https://docs.wavestreamer.ai)
