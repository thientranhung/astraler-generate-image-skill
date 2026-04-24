---
name: astraler-generate-image
description: >
  Astraler's image generation skill — generates images via Google Gemini/Imagen API
  OR OpenAI GPT-image models (gpt-image-1, gpt-image-1-mini, gpt-image-1.5).

  ONLY activate this skill when user explicitly mentions "Astraler" in an image generation context.

  GOOGLE / GEMINI trigger phrases:
    "Astraler tạo ảnh", "Astraler vẽ", "dùng Astraler generate image",
    "Astraler draw", "Astraler image", "tạo ảnh bằng Astraler",
    "nhờ Astraler vẽ", "Astraler vẽ cho tôi", "dùng Astraler để vẽ",
    "Astraler create image", "astraler generate", "astraler picture", "astraler art",
    "astraler gemini", "astraler imagen".

  OPENAI / GPT-IMAGE trigger phrases (route to OpenAI API):
    "astraler image gpt", "astraler image openai", "astraler gpt image",
    "astraler openai", "astraler dùng openai", "astraler gpt-image",
    "astraler image gpt-image-1", "astraler chatgpt image",
    "astraler vẽ bằng openai", "astraler tạo ảnh openai".

  Do NOT trigger for generic image requests without the word "Astraler".
  Supports aspect ratios: 1:1 (default), 16:9, 9:16, 4:3, 3:4.
allowed-tools: Read, Bash
---

# Astraler Generate Image

Astraler's image generation skill — creates high-quality images via:
- **Google Gemini / Imagen 4** (default) — uses `GEMINI_API_KEY`
- **OpenAI GPT-image models** — uses `OPENAI_API_KEY`

---

## Instructions

### Step 0: Detect provider from user's request

| User says | Provider | Default model |
|---|---|---|
| "astraler image gpt", "astraler openai", "astraler chatgpt image", "astraler gpt-image-2" … | OpenAI | `gpt-image-2` |
| "astraler vẽ", "astraler image", "astraler gemini", "astraler imagen" … | Google | `gemini-3-pro-image-preview` |

### Step 1: Locate skill directory + verify API key

```bash
SKILL_DIR=$(find "$HOME/.gemini/antigravity/skills/astraler-generate-image" -maxdepth 0 2>/dev/null \
  || find "$HOME/.claude/skills/astraler-generate-image" -maxdepth 0 2>/dev/null)
echo "Skill dir: $SKILL_DIR"
cat "$SKILL_DIR/.env"
```

**For Google (Gemini/Imagen):** needs `GEMINI_API_KEY`
- Get free key: https://aistudio.google.com/app/apikey

**For OpenAI (GPT-image):** needs `OPENAI_API_KEY`
- Get key: https://platform.openai.com/api-keys

Configure in `$SKILL_DIR/.env`:
```
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

### Step 2: Craft a detailed prompt

Enhance the user's prompt with quality modifiers:
- Style: `cinematic lighting`, `4K`, `photorealistic`, `high detail`
- Keep it descriptive and specific

### Step 3: Determine aspect ratio

| Ratio | Use case |
|-------|----------|
| `1:1` | Square — social media (default) |
| `16:9` | Landscape / widescreen |
| `9:16` | Portrait / mobile / Stories |
| `4:3` | Classic / presentation |
| `3:4` | Tall portrait |

### Step 4: Run the script

**Google Gemini/Imagen (default):**
```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "your enhanced prompt here" \
  --output "output.png" \
  --aspect_ratio "16:9"
```

**OpenAI GPT-image models:**
```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "your enhanced prompt here" \
  --output "output.png" \
  --aspect_ratio "16:9" \
  --model "gpt-image-1" \
  --quality "high" \
  --format "png"
```

The `--provider` flag is auto-detected from the model name, but can be set explicitly:
```bash
  --provider openai   # or google
```

### Step 5: Report to user

Tell the user: file path, model used, prompt, token usage (OpenAI only), and offer to refine.

---

## Examples

### Example 1: OpenAI GPT-image landscape
**User asks**: "astraler image gpt vẽ thành phố cyberpunk về đêm, 16:9"

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "a highly detailed cyberpunk city at night, neon lights reflecting on wet streets, flying cars, cinematic lighting, 4K, photorealistic" \
  --output "cyberpunk_city.png" \
  --model "gpt-image-2" \
  --aspect_ratio "16:9" \
  --quality "high"
```

### Example 2: OpenAI GPT-image portrait
**User asks**: "astraler openai tạo chân dung anime 9:16"

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "anime style portrait of a young woman with long black hair, soft lighting, detailed eyes, studio ghibli inspired" \
  --output "anime_portrait.png" \
  --model "gpt-image-2" \
  --aspect_ratio "9:16" \
  --quality "medium"
```

### Example 3: OpenAI gpt-image-1-mini (faster/cheaper)
**User asks**: "astraler chatgpt image vẽ logo minimalist"

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "minimalist modern logo, clean lines, geometric shapes, white background" \
  --output "logo.png" \
  --model "gpt-image-1-mini" \
  --aspect_ratio "1:1" \
  --quality "medium"
```

### Example 4: Google Imagen 4 (default path)
**User asks**: "Astraler vẽ ảnh núi lúc hoàng hôn, Imagen 4"

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "majestic mountain landscape at sunset, golden hour, dramatic clouds, epic scale" \
  --output "mountain_sunset.png" \
  --aspect_ratio "16:9" \
  --model "imagen-4.0-generate-001"
```

---

## Model Reference

### OpenAI GPT-image models

| Model | Quality | Speed | Notes |
|-------|---------|-------|-------|
| `gpt-image-2` | ⭐⭐⭐⭐⭐ | Medium | **Default**, latest generation ✅ |
| `gpt-image-1.5` | ⭐⭐⭐⭐⭐ | Medium | Previous gen, high quality |
| `gpt-image-1` | ⭐⭐⭐⭐ | Medium | Stable, widely supported |
| `gpt-image-1-mini` | ⭐⭐⭐ | Fast | Cheaper, good for drafts |

**Sizes for GPT-image:**
- `1:1` → `1024x1024`
- `16:9` → `1536x1024` (landscape)
- `9:16` → `1024x1536` (portrait)

**Quality options:** `low` | `medium` | `high` | `auto`  
**Format options:** `png` | `jpeg` | `webp`  
**Response:** Always returns base64-encoded image (no URL)

### Google Gemini / Imagen models

| Model | Quality | Notes |
|-------|---------|-------|
| `gemini-3-pro-image-preview` | ⭐⭐⭐⭐⭐ | Default, reliable |
| `gemini-3.1-flash-image-preview` | ⭐⭐⭐⭐ | Faster |
| `imagen-4.0-generate-001` | ⭐⭐⭐⭐⭐ | Highest quality (Imagen 4) |
| `imagen-4.0-fast-generate-001` | ⭐⭐⭐⭐ | Imagen 4 Fast |

---

## Limitations

- **OpenAI:** Requires `OPENAI_API_KEY`. GPT-image models always return base64 (no URL response).
- **Google:** Requires `GEMINI_API_KEY`. Free tier at Google AI Studio.
- Both providers: Content must comply with their respective usage policies.
- Script requires Python 3.8+ (stdlib only — no `pip install` needed).

---

## Configuration (`.env` file)

```
# Google Gemini / Imagen
GEMINI_API_KEY=your_google_key_here

# OpenAI GPT-image
OPENAI_API_KEY=your_openai_key_here

# Default model (used when --model is not specified)
IMAGE_MODEL=gemini-3-pro-image-preview
```

See [references/models.md](references/models.md) for detailed model specs.
