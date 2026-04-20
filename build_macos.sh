#!/usr/bin/env bash
# =============================================================================
# build_macos.sh  –  Build SWUIFT.app for macOS (arm64 and/or x86_64)
#
# Usage:
#   ./build_macos.sh              # builds for current host architecture
#   ./build_macos.sh arm64        # explicitly build arm64
#   ./build_macos.sh x86_64       # explicitly build x86_64
#   ./build_macos.sh universal    # build both, then lipo into a universal app
#
# Prerequisites:
#   - Python 3.10+ with a virtualenv at .venv (create with:
#       python3 -m venv .venv && .venv/bin/pip install -r requirements_app.txt)
#   - For universal builds, both arm64 and x86_64 Python environments are needed
#     OR you must build on each machine separately and combine afterwards.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV=".venv/bin"
PYINSTALLER="$VENV/pyinstaller"
SPEC="swuift_app.spec"
DIST_DIR="dist"

TARGET_ARCH="${1:-native}"

echo "========================================"
echo " SWUIFT macOS build"
echo " Target architecture: $TARGET_ARCH"
echo "========================================"

# ── Generate SWUIFT.ico (for Windows, needed by spec even on macOS) ─────────
if [ ! -f SWUIFT.ico ]; then
    echo "Generating SWUIFT.ico from SWUIFT.icns …"
    "$VENV/python" -c "
from PIL import Image
img = Image.open('SWUIFT.icns')
img.save('SWUIFT.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('  SWUIFT.ico created')
"
fi

build_arch() {
    local arch="$1"
    local out_dir="${DIST_DIR}_${arch}"

    echo ""
    echo "── Building for $arch …"
    echo ""

    mkdir -p "$out_dir"

    if [ "$arch" = "arm64" ]; then
        ARCH_CMD="arch -arm64"
    elif [ "$arch" = "x86_64" ]; then
        ARCH_CMD="arch -x86_64"
    else
        ARCH_CMD=""
    fi

    # Run pyinstaller under the requested arch slice.
    $ARCH_CMD "$PYINSTALLER" "$SPEC" \
        --noconfirm \
        --clean \
        --distpath "$out_dir"

    echo ""
    echo "── Build for $arch complete: $out_dir/SWUIFT.app"
}

create_dmg() {
    local arch="$1"
    local app_path="${DIST_DIR}_${arch}/SWUIFT.app"
    local dmg_path="${DIST_DIR}/SWUIFT_macOS_${arch}.dmg"

    if [ ! -d "$app_path" ]; then
        echo "WARNING: $app_path not found, skipping DMG creation."
        return
    fi

    echo ""
    echo "── Creating DMG for $arch …"
    mkdir -p "$DIST_DIR"

    # Create a temporary mount point.
    TMPDIR_DMG=$(mktemp -d)
    cp -r "$app_path" "$TMPDIR_DMG/"

    hdiutil create \
        -volname "SWUIFT" \
        -srcfolder "$TMPDIR_DMG" \
        -ov \
        -format UDZO \
        "$dmg_path"

    rm -rf "$TMPDIR_DMG"
    echo "── DMG created: $dmg_path"
}

if [ "$TARGET_ARCH" = "universal" ]; then
    build_arch "arm64"
    build_arch "x86_64"

    echo ""
    echo "── Creating universal binary with lipo …"
    # lipo only applies to the bare executable; the .app itself is
    # effectively arch-specific unless every Python extension inside it
    # is universal.  Shipping two separate .app bundles is more reliable.
    echo "NOTE: Native extensions (h5py, av, etc.) require building each"
    echo "      architecture separately.  Consider distributing two DMGs."

    create_dmg "arm64"
    create_dmg "x86_64"

elif [ "$TARGET_ARCH" = "arm64" ]; then
    build_arch "arm64"
    create_dmg "arm64"

elif [ "$TARGET_ARCH" = "x86_64" ]; then
    build_arch "x86_64"
    create_dmg "x86_64"

else
    # Native build
    NATIVE_ARCH=$(uname -m)
    mkdir -p "$DIST_DIR"
    "$PYINSTALLER" "$SPEC" --noconfirm --clean
    echo ""
    echo "── Native build ($NATIVE_ARCH) complete: dist/SWUIFT.app"

    if command -v hdiutil &>/dev/null; then
        create_dmg_simple() {
            local app_path="${DIST_DIR}/SWUIFT.app"
            local dmg_path="${DIST_DIR}/SWUIFT_macOS_${NATIVE_ARCH}.dmg"
            [ -d "$app_path" ] || return
            echo "── Creating DMG …"
            TMPDIR_DMG=$(mktemp -d)
            cp -r "$app_path" "$TMPDIR_DMG/"
            hdiutil create -volname "SWUIFT" -srcfolder "$TMPDIR_DMG" -ov -format UDZO "$dmg_path"
            rm -rf "$TMPDIR_DMG"
            echo "── DMG created: $dmg_path"
        }
        create_dmg_simple
    fi
fi

echo ""
echo "========================================"
echo " Build finished."
echo "========================================"
