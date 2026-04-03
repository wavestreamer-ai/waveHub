# Package Migration: Monorepo to WaveHub

This documents the package relinking from the private monorepo to the WaveHub public repo.

## What moved

| Package | Old location | New location | npm/PyPI name | Breaking change? |
|---------|-------------|-------------|---------------|-----------------|
| Python SDK | `wavestreamer/agents/` | `wavehub/sdk/` | `wavestreamer` | No |
| MCP Server | `wavestreamer/mcp/` | `wavehub/mcp/` | `@wavestreamer-ai/mcp` | No |
| LangChain | `wavestreamer/langchain-wavestreamer/` | `wavehub/langchain/` | `langchain-wavestreamer` | No |
| Runner | *NEW* (extracted from fleet) | `wavehub/runner/` | `wavehub` | N/A (new package) |

## What changed in package configs

### Python SDK (`pyproject.toml`)
```diff
[project.urls]
-Repository = "https://wavestreamer.ai"
+Repository = "https://github.com/wavestreamer-ai/waveHub"
```

### MCP Server (`package.json`)
```diff
-"repository": { "type": "git", "url": "..." }
+"repository": { "type": "git", "url": "https://github.com/wavestreamer-ai/waveHub.git", "directory": "mcp" }
```

### LangChain (`pyproject.toml`)
```diff
[project.urls]
-Repository = "..."
+Repository = "https://github.com/wavestreamer-ai/waveHub"
```

## CI/CD

- The monorepo **stops publishing** these packages
- WaveHub repo CI publishes on git tags:
  - `sdk-v*` → PyPI `wavestreamer`
  - `mcp-v*` → npm `@wavestreamer-ai/mcp`
  - `langchain-v*` → PyPI `langchain-wavestreamer`
  - `runner-v*` → PyPI `wavehub`

## For users

Nothing changes. Same `pip install wavestreamer`, same `npx @wavestreamer-ai/mcp`. The GitHub URL in package metadata changes, that's it.

## Monorepo cleanup

After migration:
1. Remove `wavestreamer/agents/` (or replace with symlink/submodule)
2. Remove `wavestreamer/mcp/` (or replace)
3. Remove `wavestreamer/langchain-wavestreamer/` (or replace)
4. Update Mintlify docs GitHub links
5. Update CLAUDE.md references
