#!/bin/bash
# Publish tombstone releases for retired package names.
#
# Each tombstone is version 999.0.0 — high enough that pip upgrade won't touch it
# but the package exists so existing installs get a redirect dependency.
#
# Requires: PYPI_TOKEN_SDK env var (or PYPI_TOKEN_LEGACY if separate)
#
# Usage:
#   ./scripts/deprecate-legacy.sh              Publish all tombstones
#   ./scripts/deprecate-legacy.sh wavestreamer Publish one tombstone
#   ./scripts/deprecate-legacy.sh --dry-run    Show what would be published

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEGACY_DIR="$REPO_ROOT/legacy"
DRY_RUN=false

for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN=true
    fi
done

if [ -z "${PYPI_TOKEN_SDK:-}" ] && [ -z "${PYPI_TOKEN_LEGACY:-}" ]; then
    echo "Error: set PYPI_TOKEN_SDK or PYPI_TOKEN_LEGACY before running this script."
    echo "  export PYPI_TOKEN_SDK=pypi-..."
    exit 1
fi

TOKEN="${PYPI_TOKEN_LEGACY:-$PYPI_TOKEN_SDK}"

PACKAGES=(wavestreamer langchain-wavestreamer)

publish_tombstone() {
    local pkg=$1
    local dir="$LEGACY_DIR/$pkg"

    if [ ! -d "$dir" ]; then
        echo "  Skipping $pkg — no directory at $dir"
        return
    fi

    echo "  Building tombstone for: $pkg"
    if [ "$DRY_RUN" = true ]; then
        echo "  [dry-run] Would build + upload $pkg 999.0.0"
        return
    fi

    pushd "$dir" > /dev/null
    rm -rf dist/
    python3 -m build --quiet
    twine upload dist/* \
        --username __token__ \
        --password "$TOKEN" \
        --skip-existing
    popd > /dev/null
    echo "  Published: $pkg 999.0.0"
}

# Filter by arg if provided
TARGETS=()
for arg in "$@"; do
    if [ "$arg" != "--dry-run" ]; then
        TARGETS+=("$arg")
    fi
done

if [ ${#TARGETS[@]} -eq 0 ]; then
    TARGETS=("${PACKAGES[@]}")
fi

echo "Publishing tombstone releases (999.0.0) for retired package names..."
pip install build twine -q

for pkg in "${TARGETS[@]}"; do
    publish_tombstone "$pkg"
done

echo ""
echo "Done. Users who pip install these names will get a redirect to the new package."
echo "To also yank old versions: go to pypi.org → project → Releases → yank each version"
