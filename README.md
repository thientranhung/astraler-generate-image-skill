# @astraler/generate-image-skill

> Astraler's image generation skill for AI agents — generates high-quality images using Google Gemini / Imagen 4 API

[![npm version](https://badge.fury.io/js/%40astraler%2Fgenerate-image-skill.svg)](https://www.npmjs.com/package/@astraler/generate-image-skill)

## Installation

```bash
npx skills add thientranhung/astraler-generate-image-skill
```

The `skills` CLI will guide you through the installation interactively — asking whether to install globally (`~/.agents/skills/`) or at project level (`.agents/skills/`).

### Update

```bash
# Global
npx skills update astraler-generate-image -g

# Project
npx skills update astraler-generate-image
```

### Uninstall

```bash
# Global
npx skills remove astraler-generate-image -g

# Project
npx skills remove astraler-generate-image
```

---

## Configuration

After installation, set your Gemini API key:

```bash
# If installed globally
nano ~/.agents/skills/astraler-generate-image/.env

# If installed at project level
nano .agents/skills/astraler-generate-image/.env

# Set: GEMINI_API_KEY=your_key_here
```

Get a **free API key** at: https://aistudio.google.com/app/apikey

---

## Usage

After configuration, talk to your AI agent:

```
"Astraler tạo ảnh một thành phố cyberpunk về đêm"
"nhờ Astraler vẽ ảnh núi tuyết, tỷ lệ 16:9"
"dùng Astraler generate image of a coffee shop logo"
"Astraler draw me an anime portrait"
```

> **Note:** This skill only activates when you say **"Astraler"** — generic image requests use the platform's built-in tool.

---

## Available Models

| Model | Quality | Notes |
|---|---|---|
| `gemini-3-pro-image-preview` | ⭐⭐⭐⭐⭐ | **Default** — best for UGC, lifestyle, photorealistic |
| `gemini-3.1-flash-image-preview` | ⭐⭐⭐⭐ | Newer, faster variant |
| `gemini-2.5-flash-image` | ⭐⭐⭐⭐ | Gemini 2.5 Flash image model |
| `imagen-4.0-generate-001` | ⭐⭐⭐⭐⭐ | Imagen 4 — highest technical quality, best for commercial/product shots |
| `imagen-4.0-fast-generate-001` | ⭐⭐⭐⭐ | Imagen 4 Fast — quicker generation |

> ~~`imagen-3.0-generate-002`~~ — **NOT available** via AI Studio API ❌

## Supported Aspect Ratios

`1:1` · `16:9` · `9:16` · `4:3` · `3:4`

---

## Requirements

- Python 3.8+
- Gemini API Key (free tier available)

---

## License

MIT
