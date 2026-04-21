# @astraler/generate-image-skill

> Astraler's image generation skill for Claude Code — generates high-quality images using Google Gemini / Imagen 3 API

[![npm version](https://badge.fury.io/js/%40astraler%2Fgenerate-image-skill.svg)](https://www.npmjs.com/package/@astraler/generate-image-skill)

## Installation

```bash
npx skills add thientranhung/astraler-generate-image-skill
```

The `skills` CLI will guide you through the installation interactively — asking whether to install globally (`~/.claude/skills/`) or at project level (`.claude/skills/`).

### Update

```bash
npx skills update @astraler/generate-image-skill
```

### Uninstall

```bash
npx skills remove @astraler/generate-image-skill
```

---

## Configuration

After installation, set your Gemini API key:

```bash
nano ~/.claude/skills/astraler-generate-image/.env
# Set: GEMINI_API_KEY=your_key_here
```

Get a **free API key** at: https://aistudio.google.com/app/apikey

---

## Usage

After configuration, talk to Claude Code:

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
| `imagen-3.0-generate-002` | ⭐⭐⭐⭐⭐ | Default, highest quality |
| `gemini-2.0-flash-exp` | ⭐⭐⭐ | Faster, experimental |

## Supported Aspect Ratios

`1:1` · `16:9` · `9:16` · `4:3` · `3:4`

---

## Requirements

- Python 3.8+
- Gemini API Key (free tier available)

---

## License

MIT
