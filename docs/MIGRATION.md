# Package Migration — COMPLETED

All packages have been migrated from the private monorepo to the WaveHub public repo. Migration is complete as of 2026-04-08.

## Current Packages (all published from wavehub)

| Directory | Package | Registry | Install |
|-----------|---------|----------|---------|
| `gnarly-sdk/` | `wavestreamer-sdk` | PyPI | `pip install wavestreamer-sdk` |
| `shaka-mcp/` | `@wavestreamer-ai/mcp` | npm | `npx @wavestreamer-ai/mcp` |
| `quiver-langchain/` | `wavestreamer-langchain` | PyPI | `pip install wavestreamer-langchain` |
| `aerial-runner/` | `wavestreamer-runner` | PyPI | `pip install wavestreamer-runner` |
| `wave-ts/` | `@wavestreamer-ai/sdk` | npm | `npm install @wavestreamer-ai/sdk` |
| `reef-crewai/` | `wavestreamer-crewai` | PyPI | `pip install wavestreamer-crewai` |

## Old Names (DO NOT USE)

| Old Name | Replaced By | Status |
|----------|-------------|--------|
| `wavestreamer` (PyPI) | `wavestreamer-sdk` | Deprecated on PyPI — do not publish to it |
| `langchain-wavestreamer` (PyPI) | `wavestreamer-langchain` | Deprecated on PyPI — do not publish to it |
| `@wavestreamer/mcp` (npm) | `@wavestreamer-ai/mcp` | Old scope deleted |
| `wavehub` (PyPI) | `wavestreamer-runner` | Old name abandoned |

## CI/CD

All publishing happens from `wavehub/.github/workflows/publish.yml` via git tags:

```
gnarly-sdk-v*      → PyPI: wavestreamer-sdk
shaka-mcp-v*       → npm: @wavestreamer-ai/mcp
quiver-langchain-v* → PyPI: wavestreamer-langchain
aerial-runner-v*   → PyPI: wavestreamer-runner
wave-ts-v*         → npm: @wavestreamer-ai/sdk
reef-crewai-v*     → PyPI: wavestreamer-crewai
```

The private `wavestreamer/` repo has zero publish responsibility. No stale pipelines remain.
