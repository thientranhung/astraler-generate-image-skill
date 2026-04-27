---
name: astraler-generate-image
description: >
  Astraler's image generation skill — generates images via Google Gemini/Imagen 4 API
  OR OpenAI GPT-image models (gpt-image-1, gpt-image-1-mini, gpt-image-1.5).
  ONLY activate this skill when user explicitly mentions "Astraler" in an image generation
  context. Performs structured prompt enhancement before generation for higher-quality
  output. Returns a JSON line with output path so calling agents can render the result.
  Supports aspect ratios: 1:1 (default), 16:9, 9:16, 4:3, 3:4.
allowed-tools: Read, Bash
---

# Astraler Generate Image

Multi-provider image generator designed to be called from agent harnesses
(Obsidian Agent Client, Antigravity, Claude Code). The skill **enhances the
user's raw prompt** with a structured framework before calling the image API,
then returns a JSON line on stdout that the calling agent can parse to render
or attach the image.

- **Google Gemini / Imagen 4** (default) — uses `GEMINI_API_KEY`
- **OpenAI GPT-image models** — uses `OPENAI_API_KEY`

## Trigger Phrases

> Only activate this skill when the user explicitly mentions **"Astraler"** in an image generation context.

**Google / Gemini (default):** `"Astraler tạo ảnh"`, `"Astraler vẽ"`, `"dùng Astraler generate image"`, `"Astraler draw"`, `"Astraler image"`, `"tạo ảnh bằng Astraler"`, `"nhờ Astraler vẽ"`, `"Astraler vẽ cho tôi"`, `"dùng Astraler để vẽ"`, `"Astraler create image"`, `"astraler gemini"`, `"astraler imagen"`

**OpenAI / GPT-image:** `"astraler image gpt"`, `"astraler image openai"`, `"astraler gpt image"`, `"astraler openai"`, `"astraler dùng openai"`, `"astraler gpt-image"`, `"astraler image gpt-image-1"`, `"astraler chatgpt image"`, `"astraler vẽ bằng openai"`, `"astraler tạo ảnh openai"`

---

## Workflow

### Step 0 — Detect provider

| User says | Provider | Default model |
|---|---|---|
| "astraler image gpt", "astraler openai", "astraler chatgpt image", "astraler gpt-image-1" … | OpenAI | `gpt-image-1` |
| "astraler vẽ", "astraler image", "astraler gemini", "astraler imagen" … | Google | `gemini-3-pro-image-preview` |

If the user explicitly names a model (e.g. "astraler dùng imagen 4", "astraler gpt-image-1.5"), use that instead.

### Step 1 — Locate skill directory + verify API key

The script auto-resolves `.env` from these locations (first hit wins):
1. `--env_file` flag
2. `$ASTRALER_SKILL_DIR/.env`
3. `<script_dir>/../.env` (normal install)
4. `~/.claude/skills/astraler-generate-image/.env`
5. `~/.gemini/antigravity/skills/astraler-generate-image/.env`
6. `~/.agents/skills/astraler-generate-image/.env`
7. `./.env`

You usually don't need to do anything — just locate the skill directory for invoking the script:

```bash
SKILL_DIR=$(ls -d "$HOME"/.gemini/antigravity/skills/astraler-generate-image \
                  "$HOME"/.claude/skills/astraler-generate-image \
                  "$HOME"/.agents/skills/astraler-generate-image 2>/dev/null | head -1)
echo "Skill dir: $SKILL_DIR"
```

If neither key is set, tell the user how to configure it:
- **Google:** `GEMINI_API_KEY` — free tier at https://aistudio.google.com/app/apikey
- **OpenAI:** `OPENAI_API_KEY` — https://platform.openai.com/api-keys

### Step 2 — Enhance the prompt (most important step)

This is what makes Astraler produce noticeably better images than a raw API
call. The user's request is usually short ("vẽ con mèo", "logo coffee shop").
Image models reward **specificity** — they fill in unspecified details with
generic priors, which is why naive prompts produce generic output.

**Build the enhanced prompt by mentally filling in this 7-component framework.**
You don't need to include every component every time, but consciously consider
each one and add what's relevant for the user's intent:

| # | Component | What to add | Example |
|---|---|---|---|
| 1 | **Subject** | Concrete details: age, expression, clothing, action, breed/species, count | "an orange tabby cat", "a young Vietnamese woman in áo dài" |
| 2 | **Composition** | Shot type, framing, camera angle, focal point | "close-up portrait", "wide establishing shot", "low angle, rule of thirds" |
| 3 | **Style / Medium** | Art style or rendering medium | "photorealistic", "studio Ghibli anime", "oil painting", "3D Pixar render", "watercolor" |
| 4 | **Lighting** | Light direction, quality, color temperature | "golden hour sunlight", "soft rim lighting", "dramatic chiaroscuro", "cool neon glow" |
| 5 | **Mood / Atmosphere** | Emotional tone, environment feel | "serene", "ominous", "playful", "cyberpunk dystopia" |
| 6 | **Technical** (photoreal only) | Camera/lens, depth, sharpness — skip for stylized work | "shot on 85mm f/1.4", "shallow depth of field, sharp focus on eyes" |
| 7 | **Negative hints** | Things to exclude (helpful for Gemini text models) | "no text, no watermark, no extra fingers" |

**Important — DON'T over-enhance:**
- If the user already wrote a long, detailed prompt, leave it alone or only lightly polish. They have specific intent.
- If the user said `--no_enhance` or "raw", "đừng enhance", "giữ nguyên prompt", skip enhancement — pass the raw prompt through.
- Don't add components that conflict with the user's intent (e.g. don't add "photorealistic" if they asked for cartoon).

**Provider-specific style:**

- **Imagen 4** (`imagen-4.0-*`) — prefers **flowing natural-language sentences**, not keyword lists. Write as if describing a scene to a human. Multilingual works but English produces slightly more reliable composition.
- **Gemini image preview** (`gemini-*-image-preview`) — handles **Vietnamese natively**; you don't need to translate. Add aspect-ratio context inside the prompt if the user cared about it.
- **GPT-image-1 / 1.5** — prefers **structured, comma-separated phrases** and labeled sections. Concise > verbose. Reads `Subject: …, Style: …, Lighting: …, Composition: …` very well.
- **GPT-image-1-mini** — keep enhanced prompt **shorter** (the smaller model gets confused by very long prompts). Hit the top 3-4 components only.

### Step 3 — Determine aspect ratio

| Ratio | Use case |
|-------|----------|
| `1:1` | Square — social, default |
| `16:9` | Landscape, banner, widescreen |
| `9:16` | Portrait, mobile, Stories/TikTok |
| `4:3` | Classic, presentation |
| `3:4` | Tall portrait |

If the user didn't specify, default to `1:1` for portraits/single subjects, `16:9` for landscapes/scenes.

### Step 4 — Run the script

The script always emits a final single-line JSON on stdout. Add `--enhanced_from` to record the user's original prompt for traceability — the calling agent can show it back to the user.

**Google Gemini / Imagen (default):**
```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "<your enhanced prompt>" \
  --enhanced_from "<user's original raw request>" \
  --output "output.png" \
  --aspect_ratio "16:9"
```

**OpenAI GPT-image:**
```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "<your enhanced prompt>" \
  --enhanced_from "<user's original raw request>" \
  --output "output.png" \
  --aspect_ratio "16:9" \
  --model "gpt-image-1" \
  --quality "high" \
  --format "png"
```

**Useful flags:**
- `--json` — emit *only* the final JSON line (useful when called from another script that parses output strictly)
- `--quiet` — suppress decorative banner (still prints the JSON line)
- `--background transparent` — OpenAI only, transparent PNG/WebP output
- `--env_file <path>` — explicit .env override

### Step 5 — Parse the JSON line and report

The last stdout line is always JSON. Parse it and report:
- File path — **always read this from `output_path` in the JSON, not the `--output` flag you passed**. Some Google models (e.g. `gemini-3-pro-image-preview`) return JPEG inline data even if the user requested `.png`; the script rewrites the extension to match the actual MIME so callers always get a valid file.
- Model used
- The enhanced prompt (so the user can iterate)
- Token usage (OpenAI only)

**Success shape:**
```json
{
  "ok": true,
  "provider": "openai",
  "model": "gpt-image-1",
  "output_path": "/abs/path/to/output.png",
  "size": "1536x1024",
  "aspect_ratio": "16:9",
  "quality": "high",
  "format": "png",
  "mime": "image/png",
  "bytes_size": 1843204,
  "prompt": "<enhanced prompt that was sent>",
  "enhanced_from": "<user's raw request>",
  "usage": {"total_tokens": 1234, "input_tokens": 50, "output_tokens": 1184},
  "duration_ms": 8420
}
```

**Failure shape:**
```json
{"ok": false, "error": "...", "provider": "openai", "model": "gpt-image-1"}
```

When `ok: true`, return the `output_path` to the caller so the harness can render the image. Offer to refine (different style, ratio, model).

---

## Prompt Enhancement Examples

### Example A — Casual, brief request (typical case)

**User:** `"Astraler vẽ con mèo"`

**Enhanced for Imagen 4 / Gemini (natural sentence):**
> A fluffy orange tabby cat sitting on a wooden windowsill, looking out at a misty morning garden, soft golden-hour sunlight streaming through the window, warm bokeh background, photorealistic, sharp focus on whiskers and amber eyes, peaceful and serene mood.

**Enhanced for GPT-image-1 (structured):**
> Subject: orange tabby cat, fluffy fur, sitting on wooden windowsill, looking outside.
> Style: photorealistic.
> Lighting: warm golden-hour sunlight from window.
> Composition: medium close-up, soft bokeh background.
> Mood: peaceful, serene morning.

### Example B — Logo / minimalist (don't over-photograph)

**User:** `"astraler chatgpt image vẽ logo cafe minimalist"`

**Enhanced (skip Lighting/Technical — irrelevant for vector logo):**
> Subject: minimalist coffee shop logo, single coffee cup with rising steam, geometric clean lines.
> Style: flat vector logo, modern, monochromatic.
> Composition: centered, generous white space, balanced negative space.
> Negative: no text, no photograph, no shading, no 3D effects.

### Example C — Cyberpunk scene (heavy on Mood + Lighting)

**User:** `"astraler image gpt vẽ thành phố cyberpunk về đêm 16:9"`

**Enhanced for GPT-image-1:**
> Subject: dense cyberpunk megacity at night, towering skyscrapers covered in holographic billboards, neon Chinese and Japanese signs, flying cars streaking through the sky, lone figure in trenchcoat on rain-slick street.
> Style: cinematic photorealistic, Blade Runner 2049 inspired.
> Lighting: vibrant neon glow — magenta, cyan, electric blue — reflecting on wet asphalt.
> Composition: wide establishing shot, low angle, deep depth field.
> Mood: dystopian, atmospheric, mysterious.

### Example D — User already wrote detailed prompt (don't over-enhance)

**User:** `"Astraler vẽ giúp: A serene Japanese zen garden in early autumn, raked white sand patterns, three weathered moss-covered stones, single red maple tree shedding leaves onto the sand, traditional bamboo fence, soft overcast morning light, shot from a slightly elevated angle"`

**Enhanced (light polish only — user already nailed it):**
> A serene Japanese zen garden in early autumn, meticulously raked concentric white sand patterns, three weathered moss-covered stones arranged in asymmetrical balance, a single red Japanese maple shedding crimson leaves onto the sand, traditional bamboo fence in the background, soft diffused overcast morning light, slightly elevated three-quarter angle, photorealistic, peaceful atmosphere.

### Example E — User says "no_enhance"

**User:** `"astraler vẽ con rồng nhưng giữ nguyên prompt: dragon"`

→ Pass `dragon` to `--prompt` unchanged. The `--enhanced_from` flag isn't needed (no enhancement happened).

---

## Model Reference

### OpenAI GPT-image

| Model | Quality | Speed | Notes |
|-------|---------|-------|-------|
| `gpt-image-1` | ⭐⭐⭐⭐⭐ | Medium | **Default**, stable & recommended ✅ |
| `gpt-image-1.5` | ⭐⭐⭐⭐⭐ | Medium | Higher-quality variant |
| `gpt-image-1-mini` | ⭐⭐⭐ | Fast | Cheaper, good for drafts — use shorter prompts |
| `gpt-image-2` | ⭐⭐⭐⭐⭐ | Medium | Requires org verification ⚠️ |

Sizes:
- `1:1` → `1024x1024`
- `16:9` / `4:3` → `1536x1024` (landscape)
- `9:16` / `3:4` → `1024x1536` (portrait)

Quality: `low` | `medium` | `high` | `auto`
Format: `png` | `jpeg` | `webp`
Background: `auto` | `transparent` | `opaque`

### Google Gemini / Imagen

| Model | Quality | Notes |
|-------|---------|-------|
| `gemini-3-pro-image-preview` | ⭐⭐⭐⭐⭐ | **Default**, reliable, multilingual |
| `gemini-3.1-flash-image-preview` | ⭐⭐⭐⭐ | Faster |
| `imagen-4.0-generate-001` | ⭐⭐⭐⭐⭐ | Highest technical quality (Imagen 4) |
| `imagen-4.0-fast-generate-001` | ⭐⭐⭐⭐ | Imagen 4 Fast |

See [references/models.md](references/models.md) for endpoints, payload shapes, and pricing notes.

---

## Configuration (`.env`)

```dotenv
# Google Gemini / Imagen
GEMINI_API_KEY=your_google_key_here

# OpenAI GPT-image
OPENAI_API_KEY=your_openai_key_here

# Default model (used when --model is not specified)
IMAGE_MODEL=gemini-3-pro-image-preview
```

## Limitations

- **OpenAI:** Requires `OPENAI_API_KEY`. GPT-image models always return base64 (no URL).
- **Google:** Requires `GEMINI_API_KEY`. Free tier at Google AI Studio.
- Both providers: Content must comply with respective usage policies.
- Script requires Python 3.8+ (stdlib only — no `pip install` needed).
