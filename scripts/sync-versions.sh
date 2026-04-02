#!/bin/bash
# Syncs VERSION file to all package manifests.
# Run before publishing: ./scripts/sync-versions.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION=$(cat "$REPO_ROOT/VERSION" | tr -d '[:space:]')

echo "Syncing version: $VERSION"

# SDK (pyproject.toml)
sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" "$REPO_ROOT/sdk/pyproject.toml"
echo "  sdk/pyproject.toml → $VERSION"

# LangChain (pyproject.toml)
sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" "$REPO_ROOT/langchain/pyproject.toml"
echo "  langchain/pyproject.toml → $VERSION"

# MCP (package.json) — use node for reliable JSON editing
node -e "
const fs = require('fs');
const p = '$REPO_ROOT/mcp/package.json';
const pkg = JSON.parse(fs.readFileSync(p, 'utf8'));
pkg.version = '$VERSION';
fs.writeFileSync(p, JSON.stringify(pkg, null, 2) + '\n');
"
echo "  mcp/package.json → $VERSION"

# Runner (pyproject.toml) — will exist after Spike 44
if [ -f "$REPO_ROOT/runner/pyproject.toml" ]; then
  sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" "$REPO_ROOT/runner/pyproject.toml"
  echo "  runner/pyproject.toml → $VERSION"
fi

echo "Done. All packages at v$VERSION"
