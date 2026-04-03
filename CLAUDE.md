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

`VERSION` file is the single source of truth. All 4 packages share the same version. Never hardcode versions.

### Release process

```bash
# 1. Work on feature branch, PR to main
# 2. After merge:
make patch            # Bumps VERSION, syncs all manifests, commits
make release          # Tags + pushes → CI tests + publishes to npm/PyPI

# Individual packages
make release-mcp      # Publish MCP only
make release-sdk      # Publish SDK only

# If CI didn't trigger on tag push
make publish PKG=all  # Manual trigger via GitHub Actions
```

### What happens

1. `make patch` → updates `VERSION` → `sync-versions.sh` writes to all 4 manifests → commits
2. `make release` → creates git tags (`shaka-mcp-v0.1.2`, etc.) → pushes tags
3. GitHub Actions `publish.yml` triggers on tag push → runs tests → publishes to npm/PyPI
4. If tags don't trigger (GitHub quirk), use `make publish PKG=all` for manual dispatch

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
