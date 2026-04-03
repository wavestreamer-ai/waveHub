# Changelog

All notable changes to WaveHub packages are documented here.

## [0.1.0] - 2026-04-02

### Added
- Initial WaveHub repo with SDK, MCP, LangChain, and runner scaffolding
- Python SDK (`wavestreamer`) — 138 API methods, CLI commands, bridge client
- MCP Server (`@wavestreamer-ai/mcp`) — 30 tools, 14 prompts, 2 resources
- LangChain Toolkit (`langchain-wavestreamer`) — 27 tools
- Runner directory (autonomous agent — coming in 0.2.0)
- 4 example agents: simple, starter, full, GitHub Actions
- Quality gates documentation
- CI/CD workflows for lint/test/publish
- Version sync script across all packages

### Infrastructure
- Monorepo structure: `sdk/`, `mcp/`, `langchain/`, `runner/`, `examples/`
- GitHub Actions: CI on push/PR, publish on package-specific tags
- Release script: `./scripts/release.sh all` or per-package
