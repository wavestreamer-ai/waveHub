#!/bin/bash
# Release a specific package or all packages.
#
# Usage:
#   ./scripts/release.sh all                Release all packages
#   ./scripts/release.sh gnarly-sdk         Release SDK only
#   ./scripts/release.sh shaka-mcp          Release MCP only
#   ./scripts/release.sh quiver-langchain   Release LangChain only
#   ./scripts/release.sh aerial-runner      Release Runner only
#   ./scripts/release.sh bump patch         Bump version, sync, tag all

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION=$(cat "$REPO_ROOT/VERSION" | tr -d '[:space:]')
DRY_RUN=false

# Check for --dry-run flag
for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN=true
        shift
    fi
done

PACKAGES=(gnarly-sdk shaka-mcp quiver-langchain aerial-runner wave-ts reef-crewai)

tag_and_push() {
    local pkg=$1
    local tag="${pkg}-v${VERSION}"
    if git rev-parse "$tag" >/dev/null 2>&1; then
        echo "  Tag $tag already exists, skipping"
        return
    fi
    if [ "$DRY_RUN" = true ]; then
        echo "  [dry-run] Would tag: $tag"
    else
        git tag -a "$tag" -m "Release ${pkg} v${VERSION}"
        echo "  Tagged: $tag"
    fi
}

case "${1:-}" in
    bump)
        shift
        PART="${1:-patch}"
        IFS='.' read -r major minor patch <<< "$VERSION"
        case "$PART" in
            major) major=$((major + 1)); minor=0; patch=0 ;;
            minor) minor=$((minor + 1)); patch=0 ;;
            patch) patch=$((patch + 1)) ;;
            *) echo "Usage: release.sh bump [major|minor|patch]"; exit 1 ;;
        esac
        NEW_VERSION="${major}.${minor}.${patch}"
        echo "$NEW_VERSION" > "$REPO_ROOT/VERSION"
        "$REPO_ROOT/scripts/sync-versions.sh"
        git add -A
        git commit -m "Bump version to ${NEW_VERSION}"
        VERSION="$NEW_VERSION"
        echo "Version bumped to $NEW_VERSION"
        echo ""
        echo "Now run: ./scripts/release.sh all"
        ;;
    all)
        echo "Releasing all packages at v${VERSION}"
        "$REPO_ROOT/scripts/sync-versions.sh"
        for pkg in "${PACKAGES[@]}"; do
            tag_and_push "$pkg"
        done
        echo ""
        if [ "$DRY_RUN" = true ]; then
            echo "[dry-run] Would push tags. No changes made."
        else
            echo "Pushing tags..."
            git push --tags
            echo "Done. CI will publish to PyPI + npm."
        fi
        ;;
    gnarly-sdk|shaka-mcp|quiver-langchain|aerial-runner|wave-ts|reef-crewai)
        echo "Releasing $1 at v${VERSION}"
        "$REPO_ROOT/scripts/sync-versions.sh"
        tag_and_push "$1"
        echo ""
        if [ "$DRY_RUN" = true ]; then
            echo "[dry-run] Would push tag. No changes made."
        else
            echo "Pushing tag..."
            git push --tags
            echo "Done. CI will publish $1 to registry."
        fi
        ;;
    *)
        echo "Usage:"
        echo "  ./scripts/release.sh all                Release all packages"
        echo "  ./scripts/release.sh gnarly-sdk         Release SDK only"
        echo "  ./scripts/release.sh shaka-mcp          Release MCP only"
        echo "  ./scripts/release.sh quiver-langchain   Release LangChain only"
        echo "  ./scripts/release.sh aerial-runner      Release Runner only"
        echo "  ./scripts/release.sh bump [patch]       Bump version first"
        echo ""
        echo "Current version: $VERSION"
        ;;
esac
