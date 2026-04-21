#!/usr/bin/env bash
# Astraler Generate Image — Uninstaller

SKILL_NAME="astraler-generate-image"
INSTALL_DIR="$HOME/.claude/skills/$SKILL_NAME"

echo ""
echo "Removing $INSTALL_DIR ..."

if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "✓ Uninstalled successfully."
else
    echo "→ Skill not found at $INSTALL_DIR (already uninstalled?)"
fi
echo ""
