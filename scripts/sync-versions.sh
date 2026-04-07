#!/bin/bash
# Syncs VERSION file to all package manifests.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION=$(cat "$REPO_ROOT/VERSION" | tr -d '[:space:]')

echo "Syncing version: $VERSION"

sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" "$REPO_ROOT/gnarly-sdk/pyproject.toml"
sed -i '' "s/^__version__ = \".*\"/__version__ = \"$VERSION\"/" "$REPO_ROOT/gnarly-sdk/wavestreamer/__init__.py"
echo "  gnarly-sdk/pyproject.toml + __init__.py → $VERSION"

sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" "$REPO_ROOT/quiver-langchain/pyproject.toml"
echo "  quiver-langchain/pyproject.toml → $VERSION"

node -e "
const fs = require('fs');
const p = '$REPO_ROOT/shaka-mcp/package.json';
const pkg = JSON.parse(fs.readFileSync(p, 'utf8'));
pkg.version = '$VERSION';
fs.writeFileSync(p, JSON.stringify(pkg, null, 2) + '\n');
"
echo "  shaka-mcp/package.json → $VERSION"

if [ -f "$REPO_ROOT/aerial-runner/pyproject.toml" ]; then
  sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" "$REPO_ROOT/aerial-runner/pyproject.toml"
  echo "  aerial-runner/pyproject.toml → $VERSION"
fi

if [ -f "$REPO_ROOT/wave-ts/package.json" ]; then
  node -e "
const fs = require('fs');
const p = '$REPO_ROOT/wave-ts/package.json';
const pkg = JSON.parse(fs.readFileSync(p, 'utf8'));
pkg.version = '$VERSION';
fs.writeFileSync(p, JSON.stringify(pkg, null, 2) + '\n');
"
  echo "  wave-ts/package.json → $VERSION"
fi

if [ -f "$REPO_ROOT/reef-crewai/pyproject.toml" ]; then
  sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" "$REPO_ROOT/reef-crewai/pyproject.toml"
  echo "  reef-crewai/pyproject.toml → $VERSION"
fi

echo "Done. All packages at v$VERSION"
