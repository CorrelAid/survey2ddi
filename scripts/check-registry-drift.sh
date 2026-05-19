#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(cat .registry-version)
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

git clone --depth 1 --branch "$VERSION" \
  https://github.com/CorrelAid/survey-type-registry.git \
  "$TMPDIR/registry" > /dev/null

if ! diff -q "$TMPDIR/registry/generated/type_mappings.py" \
              survey2ddi_core/_generated/type_mappings.py > /dev/null; then
  echo "ERROR: survey2ddi_core/_generated/type_mappings.py drifts from registry $VERSION"
  echo "Run: bash scripts/sync-registry.sh"
  exit 1
fi
echo "OK: registry sync at $VERSION."
