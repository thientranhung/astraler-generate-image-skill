---
name: astraler-generate-image
description: >
  Astraler's image generation skill — generates images via Google Gemini / Imagen 3 API.
  ONLY activate this skill when user explicitly mentions "Astraler" in an image generation context.
  Trigger phrases: "Astraler tạo ảnh", "Astraler vẽ", "dùng Astraler generate image",
  "Astraler draw", "Astraler image", "tạo ảnh bằng Astraler", "nhờ Astraler vẽ",
  "Astraler vẽ cho tôi", "dùng Astraler để vẽ", "Astraler create image",
  "astraler generate", "astraler picture", "astraler art".
  Do NOT trigger for generic image requests without the word "Astraler" — those should use the platform's built-in image tool.
  Supports aspect ratios: 1:1 (default), 16:9, 9:16, 4:3, 3:4.
allowed-tools: Read, Bash
---

# Astraler Generate Image

Astraler's image generation skill — creates high-quality images via Google's official Gemini/Imagen 3 API using a bundled Python script.

## Instructions

### Step 0: Locate the skill + verify API key

Run this to find the installed skill directory:

```bash
find "$HOME/.claude/skills/astraler-generate-image" -name "generate.py" 2>/dev/null | head -1 \
  || find "$HOME" -name "generate.py" -path "*/astraler-generate-image/scripts/*" 2>/dev/null | head -1
```

Then check if the API key is configured:

```bash
cat "$SKILL_DIR/.env" 2>/dev/null | grep GEMINI_API_KEY
```

If still showing placeholder `your_gemini_api_key_here`, ask the user to configure it:
- **Option A:** Edit `$SKILL_DIR/.env` — key persists across sessions
- **Option B:** `export GEMINI_API_KEY=their_key` in terminal — current session only
- **Option C:** Add to `~/.zshrc` — permanent

Get a free key at: https://aistudio.google.com/app/apikey

### Step 1: Craft a detailed prompt

Enhance the user's prompt with quality modifiers:
- Style: `cinematic lighting`, `4K`, `photorealistic`, `high detail`
- Keep it descriptive and specific

### Step 2: Determine aspect ratio

If not specified, ask. Common choices:
- `1:1` — square (default, social media)
- `16:9` — widescreen / landscape
- `9:16` — portrait / mobile / Story
- `4:3` — classic / presentation

### Step 3: Run the script

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "your enhanced prompt here" \
  --output "output_filename.png" \
  --aspect_ratio "16:9"
```

**Expected output:**
```
Image successfully generated and saved to output_filename.png
```

### Step 4: Report to user

Tell the user the file path, the prompt used, and offer to refine if needed.

## Examples

### Example 1: Landscape image
**User asks**: "Vẽ cho tôi một thành phố cyberpunk về đêm, tỷ lệ 16:9"

**What the skill does**:
1. Enhances prompt with cinematic quality modifiers
2. Runs script with `--aspect_ratio "16:9"`
3. Reports saved file path to user

**Command**:
```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "a highly detailed cyberpunk city at night, neon lights reflecting on wet streets, flying cars, cinematic lighting, 4K, photorealistic" \
  --output "cyberpunk_city.png" \
  --aspect_ratio "16:9"
```

### Example 2: Portrait / Avatar
**User asks**: "Tạo ảnh chân dung phong cách anime"

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "anime style portrait of a young woman with long black hair, soft lighting, detailed eyes, studio ghibli inspired" \
  --output "anime_portrait.png" \
  --aspect_ratio "9:16"
```

### Example 3: Choose specific model
**User asks**: "Dùng Imagen 3 vẽ ảnh núi lúc hoàng hôn"

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "majestic mountain landscape at sunset, golden hour, dramatic clouds, epic scale" \
  --output "mountain_sunset.png" \
  --aspect_ratio "16:9" \
  --model "imagen-3.0-generate-002"
```

## Limitations

- Requires a valid `GEMINI_API_KEY` — free tier available at Google AI Studio
- Image content must comply with Google's usage policies (no violence, explicit content)
- Script requires Python 3.8+ (uses stdlib only, no pip install needed)
- `gemini-2.0-flash-exp` may return text instead of image for some prompts — use `imagen-3.0-generate-002` for reliable image output

## Configuration

After installation, edit the `.env` file in the skill directory:

```
~/.claude/skills/astraler-generate-image/.env
```

Available options:
- `GEMINI_API_KEY`: Your Google AI Studio API key (required)
- `IMAGE_MODEL`: Default model — `imagen-3.0-generate-002` or `gemini-2.0-flash-exp`

## Additional Resources

For detailed model specs and aspect ratio reference:
- See [references/models.md](references/models.md) for available models and payloads
