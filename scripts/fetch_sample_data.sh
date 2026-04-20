#!/usr/bin/env bash
# =============================================================================
# fetch_sample_data.sh
#
# Download the SWUIFT sample input dataset from the project's GitHub
# Release, reassemble the split wind file, and verify checksums.
#
# Usage:
#   ./scripts/fetch_sample_data.sh                  # downloads into ./extracted_mat
#   DEST=/tmp/sample ./scripts/fetch_sample_data.sh
#   TAG=sample-data-v2 ./scripts/fetch_sample_data.sh
# =============================================================================
set -euo pipefail

REPO="${REPO:-utkrshkmr/swuift-py-app}"
TAG="${TAG:-sample-data-v1}"
DEST="${DEST:-$(cd "$(dirname "$0")/.." && pwd)/extracted_mat}"
BASE_URL="https://github.com/$REPO/releases/download/$TAG"

ASSETS=(
    extracted_mat_small.tar.gz
    SHA256SUMS
    wind.mat.part.aa
    wind.mat.part.ab
    wind.mat.part.ac
    wind.mat.part.ad
)

mkdir -p "$DEST"
cd "$DEST"

echo "── Downloading assets from $BASE_URL"
for asset in "${ASSETS[@]}"; do
    if [ -f "$asset" ]; then
        echo "   skip (already present): $asset"
        continue
    fi
    echo "   get: $asset"
    curl -L --fail --progress-bar -o "$asset" "$BASE_URL/$asset"
done

echo ""
echo "── Verifying split-part checksums"
grep -E ' (extracted_mat_small\.tar\.gz|wind\.mat\.part\.)' SHA256SUMS \
    | shasum -a 256 -c -

echo ""
echo "── Extracting small .mat bundle"
tar -xzf extracted_mat_small.tar.gz

echo ""
echo "── Reassembling wind.mat"
cat wind.mat.part.* > wind.mat

echo ""
echo "── Verifying reassembled wind.mat"
WIND_EXPECTED="$(grep ' wind.mat' SHA256SUMS | awk '{print $1}')"
WIND_ACTUAL="$(shasum -a 256 wind.mat | awk '{print $1}')"
if [ "$WIND_EXPECTED" = "$WIND_ACTUAL" ]; then
    echo "   OK  wind.mat matches expected SHA-256"
    rm -f wind.mat.part.* extracted_mat_small.tar.gz
    echo "   cleaned up split parts and tarball"
else
    echo "ERROR: wind.mat SHA-256 mismatch" >&2
    echo "  expected: $WIND_EXPECTED" >&2
    echo "  actual:   $WIND_ACTUAL"   >&2
    exit 1
fi

echo ""
echo "Done.  Sample dataset is in: $DEST"
ls -lh "$DEST"
