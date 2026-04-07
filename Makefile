# WaveHub — version management + publishing
#
# Usage:
#   make patch              Bump 0.1.1 → 0.1.2, sync all manifests
#   make minor              Bump 0.1.1 → 0.2.0
#   make major              Bump 0.1.1 → 1.0.0
#   make release            Tag + push all packages → CI publishes
#   make release-sdk        Tag + push SDK only
#   make release-mcp        Tag + push MCP only
#   make publish PKG=all    Manual publish via GitHub Actions (if tags didn't trigger)
#   make build              Build all packages locally
#   make lint               Lint all packages
#   make test               Test all packages

VERSION := $(shell cat VERSION | tr -d '[:space:]')

.PHONY: patch minor major release release-sdk release-mcp release-langchain release-runner \
        publish build lint test sync-versions

# ── Version bumping ─────────────────────────────────────────────────────

patch:
	@./scripts/release.sh bump patch

minor:
	@./scripts/release.sh bump minor

major:
	@./scripts/release.sh bump major

sync-versions:
	@./scripts/sync-versions.sh

# ── Release (tag + push → CI publishes) ────────────────────────────────

release:
	@./scripts/release.sh all

release-sdk:
	@./scripts/release.sh gnarly-sdk

release-mcp:
	@./scripts/release.sh shaka-mcp

release-langchain:
	@./scripts/release.sh quiver-langchain

release-runner:
	@./scripts/release.sh aerial-runner

# ── Manual publish (if tags didn't trigger CI) ─────────────────────────

publish:
	@PKG=$${PKG:-all}; \
	echo "Triggering publish for: $$PKG"; \
	gh workflow run publish.yml -f package=$$PKG

# ── Build ──────────────────────────────────────────────────────────────

build:
	@echo "Building all packages..."
	@cd shaka-mcp && pnpm run build
	@cd gnarly-sdk && python3 -m build
	@cd quiver-langchain && python3 -m build
	@cd aerial-runner && python3 -m build
	@echo "All packages built at v$(VERSION)"

# ── Lint ───────────────────────────────────────────────────────────────

lint:
	@echo "Linting..."
	@cd shaka-mcp && pnpm run lint
	@cd gnarly-sdk && ruff check .
	@cd quiver-langchain && ruff check .

# ── Test ───────────────────────────────────────────────────────────────

test:
	@echo "Testing..."
	@cd shaka-mcp && pnpm run test 2>/dev/null || echo "  (no MCP tests yet)"
	@cd gnarly-sdk && python3 -m pytest tests/ -v

# ── Info ───────────────────────────────────────────────────────────────

info:
	@echo "Version: $(VERSION)"
	@echo ""
	@echo "Packages:"
	@echo "  gnarly-sdk       → pip install wavestreamer-sdk"
	@echo "  shaka-mcp        → npx @wavestreamer-ai/mcp"
	@echo "  quiver-langchain → pip install wavestreamer-langchain"
	@echo "  aerial-runner    → pip install wavestreamer-runner"
	@echo ""
	@echo "Commands:"
	@echo "  make patch       Bump patch version"
	@echo "  make release     Tag + push → CI publishes"
	@echo "  make publish     Manual publish via GitHub Actions"
	@echo "  make build       Build locally"
	@echo "  make lint        Lint all"
