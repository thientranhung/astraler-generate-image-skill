# @astraler/generate-image-skill

> Astraler's image generation skill for AI agent harnesses (Claude Code, Antigravity, Obsidian Agent Client) — multi-provider (Google Gemini/Imagen 4 + OpenAI GPT-image), structured prompt enhancement, JSON output contract.

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

After installation, set at least one API key (Gemini OR OpenAI — both work, you can configure both):

```bash
# If installed globally
nano ~/.agents/skills/astraler-generate-image/.env

# If installed at project level
nano .agents/skills/astraler-generate-image/.env
```

```dotenv
# Google Gemini / Imagen — free tier available
GEMINI_API_KEY=your_google_key_here

# OpenAI GPT-image — paid only
OPENAI_API_KEY=your_openai_key_here

# Default model (used when --model is not specified)
IMAGE_MODEL=gemini-3-pro-image-preview
```

**Get API keys:**
- Google (free tier): https://aistudio.google.com/app/apikey
- OpenAI (paid): https://platform.openai.com/api-keys

> **Env precedence:** values already set in your harness's process environment (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `IMAGE_MODEL`) take priority over `.env` — the file only fills in keys that aren't already set. Useful when injecting keys at runtime.

---

## Usage

After configuration, talk to your AI agent. The skill activates only when you mention **"Astraler"**.

**Google Gemini / Imagen (default):**
```
"Astraler tạo ảnh một thành phố cyberpunk về đêm"
"nhờ Astraler vẽ ảnh núi tuyết, tỷ lệ 16:9"
"dùng Astraler generate image of a coffee shop logo"
"Astraler vẽ ảnh núi lúc hoàng hôn, dùng Imagen 4"
```

**OpenAI GPT-image:**
```
"astraler image gpt vẽ logo minimalist 1:1"
"astraler openai tạo chân dung anime 9:16"
"astraler chatgpt image vẽ poster phim sci-fi"
```

> The skill does structured prompt enhancement (Subject / Composition / Style / Lighting / Mood / Technical / Negative) before calling the API — short prompts like "vẽ con mèo" become detailed scene descriptions for noticeably better output. See `SKILL.md` for the full framework and provider-specific prompt-style guidance.

---

## Available Models

### Google (Gemini / Imagen)

| Model | Quality | Notes |
|---|---|---|
| `gemini-3-pro-image-preview` | ⭐⭐⭐⭐⭐ | **Default** — best for UGC, lifestyle, photorealistic; reads Vietnamese natively |
| `gemini-3.1-flash-image-preview` | ⭐⭐⭐⭐ | Faster variant |
| `imagen-4.0-generate-001` | ⭐⭐⭐⭐⭐ | Imagen 4 — highest technical quality, best for commercial / product shots |
| `imagen-4.0-fast-generate-001` | ⭐⭐⭐⭐ | Imagen 4 Fast — quicker generation |

> ~~`imagen-3.0-generate-002`~~ — **NOT available** via AI Studio API ❌

### OpenAI (GPT-image)

| Model | Quality | Notes |
|---|---|---|
| `gpt-image-1` | ⭐⭐⭐⭐⭐ | **OpenAI default** — stable, excellent for logos & vector / structured work |
| `gpt-image-1.5` | ⭐⭐⭐⭐⭐ | Higher photoreal quality |
| `gpt-image-1-mini` | ⭐⭐⭐ | Cheap & fast — good for drafts (use shorter prompts) |
| `gpt-image-2` | ⭐⭐⭐⭐⭐ | Latest — requires OpenAI org verification ⚠️ |

See `references/models.md` for endpoint shapes, payload formats, and detailed pricing notes.

---

## Supported Aspect Ratios

`1:1` (default) · `16:9` · `9:16` · `4:3` · `3:4`

> OpenAI does **not** natively support `4:3` / `3:4` — the closest landscape (`1536x1024`) or portrait (`1024x1536`) size is substituted. Google supports all 5 ratios natively.

---

## Output

The script always emits a final single-line **JSON contract** on stdout that the calling agent can parse:

```json
{
  "ok": true,
  "provider": "google",
  "model": "imagen-4.0-generate-001",
  "output_path": "/abs/path/to/output.png",
  "aspect_ratio": "16:9",
  "mime": "image/png",
  "bytes_size": 1318300,
  "prompt": "<enhanced prompt that was sent>",
  "enhanced_from": "<user's raw request>",
  "duration_ms": 4585
}
```

> **Important:** read the file path from `output_path`, not from the `--output` argument. Some Google models (e.g. `gemini-3-pro-image-preview`) return JPEG inline data even when you request a `.png`; the script honors the actual response MIME and rewrites the extension so the file on disk matches its bytes.

---

## Requirements

- Python 3.8+ (stdlib only — no `pip install`)
- At least one API key:
  - **Gemini API Key** (free tier available) — for Google models
  - **OpenAI API Key** (paid only) — for GPT-image models

---

## Distribution

This package is distributed via the **skills CLI** (`npx skills add`), **not** the npm registry. The `package.json` has `"private": true` to prevent accidental `npm publish`. The `skills` CLI pulls directly from this GitHub repo.

---

## License

MIT
