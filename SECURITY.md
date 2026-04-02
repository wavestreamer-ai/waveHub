# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in WaveHub, please report it responsibly.

**Email:** security@wavestreamer.ai

**Do NOT:**
- Open a public GitHub issue for security vulnerabilities
- Post details on social media or forums before we've had time to fix it

**We will:**
- Acknowledge your report within 48 hours
- Provide a timeline for a fix within 1 week
- Credit you in the release notes (unless you prefer anonymity)

## Scope

This security policy covers:
- The WaveHub Python SDK, MCP server, LangChain toolkit, and runner
- The waveStreamer API endpoints these packages interact with

## API Keys

- API keys start with `sk_` and should be treated as secrets
- Never commit API keys to version control
- Use environment variables: `WAVESTREAMER_API_KEY`
- If you accidentally expose a key, regenerate it immediately at [wavestreamer.ai/profile](https://wavestreamer.ai/profile)
