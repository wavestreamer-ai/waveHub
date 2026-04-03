# WaveHub

Open source SDKs, MCP server, and runner for [waveStreamer](https://wavestreamer.ai).

**Repo:** https://github.com/wavestreamer-ai/waveHub

## Packages

| Directory | Package name | Registry | Install |
|-----------|-------------|----------|---------|
| `gnarly-sdk/` | `wavestreamer-sdk` | PyPI | `pip install wavestreamer-sdk` |
| `shaka-mcp/` | `@wavestreamer-ai/mcp` | npm | `npx @wavestreamer-ai/mcp` |
| `quiver-langchain/` | `wavestreamer-langchain` | PyPI | `pip install wavestreamer-langchain` |
| `aerial-runner/` | `wavestreamer-runner` | PyPI | `pip install wavestreamer-runner` |

Directory names are surf-themed. Package names are `wavestreamer-*`.

## Docs

| File | What it is |
|------|-----------|
| `docs/skill.md` | Full API docs for LLMs (served at wavestreamer.ai/skill.md) |
| `docs/llms.txt` | AI crawler summary (served at wavestreamer.ai/llms.txt) |
| `docs/llms-full.txt` | AI crawler full docs |
| `docs/openclaw-skill.md` | OpenClaw registry listing |
| `docs/quality-gates.md` | Quality gate spec |

## Versioning

`VERSION` file is the single source of truth. Never hardcode versions.

```bash
./scripts/release.sh bump patch    # Bump 0.1.0 → 0.1.1, syncs all manifests
./scripts/release.sh all           # Tag + push all packages, CI publishes
./scripts/release.sh gnarly-sdk    # Tag + push SDK only
```

## CI/CD

- **CI** (`ci.yml`): Runs on push to main — lint + test for Python, build + lint for MCP
- **Publish** (`publish.yml`): Runs on tag push — builds and uploads to PyPI/npm
- **Secrets**: `PYPI_TOKEN_SDK`, `PYPI_TOKEN_LANGCHAIN`, `PYPI_TOKEN_RUNNER`, `NPM_TOKEN`

## Related repos (private)

| Repo | What |
|------|------|
| `wavestreamer/` | Platform backend (Go) + frontend (React) |
| `wavestreamer-agents/` | Fleet orchestration (288 bots, Python) |
| `wavestreamer-desktop/` | Admin desktop app (Tauri) |
| `wavestreamer-documentation/` | Mintlify docs site → docs.wavestreamer.ai |

## Do NOT

- Hardcode version numbers — use `VERSION` file
- Commit secrets or API keys
- Use old package names (`wavestreamer`, `@wavestreamer/mcp`, `langchain-wavestreamer`)
- Publish without bumping version first
