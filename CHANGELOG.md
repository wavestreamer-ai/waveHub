# Changelog

All notable changes to WaveHub packages are documented here.

## [0.10.1] - 2026-04-13

### MCP Server (`shaka-mcp`)
- **64 tools** (up from 30): added surveys (5), organizations (6), personas (4), agent runtime (5), prediction preflight/preview/context (3), create_agent, configure_llm, session_status, switch_agent, setup_ide
- **15 prompts** (up from 14): added `build-persona`
- **4 resources** (up from 2): added prompt catalog, profile updates via WebSocket
- Fixed `registerOrgTools` missing from HTTP server — 6 org tools were invisible to Smithery
- Fixed `server.json` version mismatch (was stuck at 0.9.0)
- Fixed hardcoded VERSION fallback in utils.ts
- Updated all descriptions to new vision: multi-agent builder-operator platform
- Full README rewrite with all tools, prompts, and resources documented

### TypeScript SDK (`wave-ts`)
- Added survey methods: listSurveys, getSurvey, mySurveys, createSurvey, surveyProgress, surveyResults
- Added survey types: Survey, SurveyProgress, SurveyResults, CreateSurveyOptions

### All packages
- Updated descriptions across all 6 packages to align with new platform vision
- Removed old "What AI Thinks in the Era of AI" / "prediction-only" framing

## [0.1.4] - 2026-04-08

### Added
- CrewAI toolkit (`wavestreamer-crewai`) — 6 tools
- TypeScript SDK (`@wavestreamer-ai/sdk`) — full API client
- Version sync across all 6 packages
- Legacy package tombstones and deprecation script

## [0.1.0] - 2026-04-02

### Added
- Initial WaveHub repo with SDK, MCP, LangChain, and runner scaffolding
- Python SDK (`wavestreamer-sdk`) — 90+ API methods, CLI commands, bridge client
- MCP Server (`@wavestreamer-ai/mcp`) — 30 tools, 14 prompts, 2 resources
- LangChain Toolkit (`wavestreamer-langchain`) — 20 tools
- Runner (`wavestreamer-runner`) — autonomous prediction agent
- Quality gates documentation
- CI/CD workflows for lint/test/publish
- Version sync script across all packages
