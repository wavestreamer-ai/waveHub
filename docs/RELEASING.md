# Releasing Packages

All 4 packages share a single version from the `VERSION` file.

## Quick Release

```bash
# 1. Bump version (patch/minor/major)
make patch                    # 0.1.1 → 0.1.2

# 2. Release all packages
make release                  # Tags + pushes → CI publishes to PyPI + npm

# Or release one package
make release-sdk              # SDK only
make release-mcp              # MCP only
make release-langchain        # LangChain only
make release-runner           # Runner only
```

## What Happens

1. `make patch` → increments `VERSION` → runs `sync-versions.sh` → commits
2. `make release` → creates git tags (`gnarly-sdk-v0.1.2`, etc.) → pushes tags
3. GitHub Actions `publish.yml` triggers on tag push → runs tests → publishes

## Dry Run

Test without making changes:

```bash
./scripts/release.sh --dry-run all
```

## Manual Publish

If tags pushed but CI didn't trigger (GitHub quirk):

```bash
make publish PKG=all          # Triggers workflow_dispatch
make publish PKG=gnarly-sdk   # Single package
```

## Version Consistency

All packages must match `VERSION`. CI checks this automatically. If they drift:

```bash
make sync-versions
```

This updates:
- `gnarly-sdk/pyproject.toml` + `wavestreamer/__init__.py`
- `shaka-mcp/package.json`
- `quiver-langchain/pyproject.toml`
- `aerial-runner/pyproject.toml`

## Registries

| Package | Registry | URL |
|---------|----------|-----|
| `wavestreamer-sdk` | PyPI | https://pypi.org/project/wavestreamer-sdk/ |
| `@wavestreamer-ai/mcp` | npm | https://www.npmjs.com/package/@wavestreamer-ai/mcp |
| `wavestreamer-langchain` | PyPI | https://pypi.org/project/wavestreamer-langchain/ |
| `wavestreamer-runner` | PyPI | https://pypi.org/project/wavestreamer-runner/ |

Smithery auto-picks up npm updates: https://smithery.ai/servers/wavestreamer-ai/shaka-mcp

## Required Secrets

Set in [repo settings](https://github.com/wavestreamer-ai/waveHub/settings/secrets/actions):

- `PYPI_TOKEN_SDK` — PyPI token for wavestreamer-sdk
- `PYPI_TOKEN_LANGCHAIN` — PyPI token for wavestreamer-langchain
- `PYPI_TOKEN_RUNNER` — PyPI token for wavestreamer-runner
- `NPM_TOKEN` — npm token for @wavestreamer-ai scope
