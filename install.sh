#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/bin"
REPO="https://raw.githubusercontent.com/vgutgutia/stardust/main/stardust"

mkdir -p "$INSTALL_DIR"

# If run from a cloned repo, copy locally; otherwise download from GitHub
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
if [ -f "$SCRIPT_DIR/stardust" ]; then
    cp "$SCRIPT_DIR/stardust" "$INSTALL_DIR/stardust"
else
    curl -fsSL "$REPO" -o "$INSTALL_DIR/stardust"
fi

chmod +x "$INSTALL_DIR/stardust"

echo ""
echo "  ✦ stardust installed to $INSTALL_DIR/stardust"
echo ""
echo "  Make sure $INSTALL_DIR is in your PATH, then run:"
echo "    stardust \"your task here\""
echo ""
