#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(cat .registry-version)
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

git clone --depth 1 --branch "$VERSION" \
  git@github.com:CorrelAid/survey-type-registry.git \
  "$TMPDIR/registry" > /dev/null 2>&1 || \
git clone --depth 1 --branch "$VERSION" \
  https://github.com/CorrelAid/survey-type-registry.git \
  "$TMPDIR/registry" > /dev/null

mkdir -p survey2ddi_core/_generated
cp "$TMPDIR/registry/generated/type_mappings.py" \
   survey2ddi_core/_generated/type_mappings.py
touch survey2ddi_core/_generated/__init__.py

echo "Synced registry $VERSION → survey2ddi_core/_generated/"
