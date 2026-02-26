#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/bin"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/stardust" "$INSTALL_DIR/stardust"
chmod +x "$INSTALL_DIR/stardust"

echo "✦ stardust installed to $INSTALL_DIR/stardust"
echo ""
echo "Make sure $INSTALL_DIR is in your PATH, then run:"
echo "  stardust \"your task here\""
