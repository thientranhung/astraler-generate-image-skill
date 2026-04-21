#!/usr/bin/env bash
# =============================================================
# Astraler Generate Image — Skill Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/tranthien/my-skills/main/astraler-generate-image/install.sh | bash
# =============================================================

set -e

SKILL_NAME="astraler-generate-image"
REPO_URL="https://github.com/tranthien/my-skills"
RAW_URL="https://raw.githubusercontent.com/tranthien/my-skills/main/astraler-generate-image"
INSTALL_DIR="$HOME/.claude/skills/$SKILL_NAME"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  Astraler Generate Image — Skill Installer${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is required but not installed.${NC}"
    echo "  Install from: https://python.org"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found: $(python3 --version)${NC}"

# Create install directory
echo -e "\n${YELLOW}→ Installing to: $INSTALL_DIR${NC}"
mkdir -p "$INSTALL_DIR/scripts"
mkdir -p "$INSTALL_DIR/references"

# Download files
echo -e "${YELLOW}→ Downloading skill files...${NC}"

download_file() {
    local url="$1"
    local dest="$2"
    if command -v curl &> /dev/null; then
        curl -fsSL "$url" -o "$dest"
    elif command -v wget &> /dev/null; then
        wget -q "$url" -O "$dest"
    else
        echo -e "${RED}✗ Neither curl nor wget found. Please install one of them.${NC}"
        exit 1
    fi
}

download_file "$RAW_URL/SKILL.md"                     "$INSTALL_DIR/SKILL.md"
download_file "$RAW_URL/scripts/generate.py"           "$INSTALL_DIR/scripts/generate.py"
download_file "$RAW_URL/references/models.md"          "$INSTALL_DIR/references/models.md"

# Create .env from template if it doesn't exist
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cat > "$INSTALL_DIR/.env" << 'ENVEOF'
# =============================================
# ASTRALER GENERATE IMAGE — API KEY CONFIG
# =============================================
# Get your free key at: https://aistudio.google.com/app/apikey
# =============================================

GEMINI_API_KEY=your_gemini_api_key_here

# Available models:
# - imagen-3.0-generate-002   : Imagen 3 (default, highest quality)
# - gemini-2.0-flash-exp      : Gemini Flash (faster, experimental)
IMAGE_MODEL=imagen-3.0-generate-002
ENVEOF
    echo -e "${GREEN}✓ Created .env template${NC}"
else
    echo -e "${YELLOW}→ .env already exists, keeping your existing config${NC}"
fi

# Make script executable
chmod +x "$INSTALL_DIR/scripts/generate.py"

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "Installed to: ${BLUE}$INSTALL_DIR${NC}"
echo ""
echo -e "${YELLOW}⚠️  Next Step — Configure your API key:${NC}"
echo ""
echo -e "  ${BLUE}nano $INSTALL_DIR/.env${NC}"
echo -e "  Set: GEMINI_API_KEY=your_key_here"
echo ""
echo -e "  Get a free key at: ${BLUE}https://aistudio.google.com/app/apikey${NC}"
echo ""
echo -e "${YELLOW}Usage in Claude Code:${NC}"
echo -e '  "Astraler vẽ ảnh một thành phố cyberpunk về đêm"'
echo -e '  "dùng Astraler generate image of a mountain, 16:9"'
echo ""
