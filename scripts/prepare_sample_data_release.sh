#!/usr/bin/env bash
# =============================================================================
# prepare_sample_data_release.sh
#
# Split the large `wind.mat`, bundle the small `.mat` files, compute
# checksums, and upload everything as assets on a GitHub Release.
#
# Run this once (or whenever the sample dataset changes) from the repo
# root.  Requires:
#   - a populated ``extracted_mat/`` with the 9 small .mat files and
#     wind.mat (see README data-inputs list)
#   - ``gh`` (https://cli.github.com) authenticated:  gh auth login
#
# Usage:
#   ./scripts/prepare_sample_data_release.sh             # tag = sample-data-v1
#   TAG=sample-data-v2 ./scripts/prepare_sample_data_release.sh
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

TAG="${TAG:-sample-data-v1}"
TITLE="${TITLE:-SWUIFT sample dataset ($TAG)}"
SRC="extracted_mat"
STAGE="build/sample_data_$TAG"
CHUNK_SIZE="1900m"         # BSD/GNU split accepts this; stays under 2 GB

if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: gh (GitHub CLI) is required.  Install from https://cli.github.com" >&2
    exit 1
fi
if [ ! -d "$SRC" ]; then
    echo "ERROR: $SRC not found.  Populate it with the 10 input .mat files first." >&2
    exit 1
fi

mkdir -p "$STAGE"

echo "── 1/4  Bundling small .mat files → $STAGE/extracted_mat_small.tar.gz"
tar -czf "$STAGE/extracted_mat_small.tar.gz" -C "$SRC" \
    binary_cover_landcover.mat \
    domain_matrix.mat \
    homes_matrix.mat \
    latitude.mat \
    longitude.mat \
    radiation_matrix.mat \
    spotting_matrix.mat \
    water_matrix.mat \
    wildland_fire_matrix.mat
du -h "$STAGE/extracted_mat_small.tar.gz"

echo ""
echo "── 2/4  Splitting $SRC/wind.mat into $CHUNK_SIZE chunks"
rm -f "$STAGE/wind.mat.part."*
( cd "$STAGE" && split -b "$CHUNK_SIZE" "../../$SRC/wind.mat" "wind.mat.part." )
ls -lh "$STAGE"/wind.mat.part.*

echo ""
echo "── 3/4  Computing SHA-256 checksums → $STAGE/SHA256SUMS"
( cd "$STAGE" && shasum -a 256 extracted_mat_small.tar.gz wind.mat.part.* > SHA256SUMS )
# Also include the pre-split wind.mat hash so users can verify the reassembled file.
echo "$(shasum -a 256 "$SRC/wind.mat" | awk '{print $1}')  wind.mat  (reassembled)" \
    >> "$STAGE/SHA256SUMS"
cat "$STAGE/SHA256SUMS"

echo ""
echo "── 4/4  Uploading to GitHub Release $TAG"
if ! gh release view "$TAG" >/dev/null 2>&1; then
    gh release create "$TAG" \
        --title "$TITLE" \
        --notes "Sample input dataset for SWUIFT.  See SAMPLE_DATA.md for download + reassembly instructions." \
        --prerelease=false
fi

gh release upload "$TAG" \
    "$STAGE/extracted_mat_small.tar.gz" \
    "$STAGE"/wind.mat.part.* \
    "$STAGE/SHA256SUMS" \
    --clobber

echo ""
echo "Done.  Release URL:"
gh release view "$TAG" --json url -q .url
