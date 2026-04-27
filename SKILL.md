---
name: astraler-generate-image
description: >
  Astraler's image generation AND editing skill — generates new images OR
  edits existing images via Google Gemini/Imagen 4 API OR OpenAI GPT-image
  models (gpt-image-1, gpt-image-1-mini, gpt-image-1.5). ONLY activate this
  skill when user explicitly mentions "Astraler" in an image generation OR
  editing context. Performs structured prompt enhancement (7-component
  framework for generation, Preserve/Change/Constraint for edits) before
  calling the API. Returns a JSON line with output path so calling agents
  can render the result. Supports aspect ratios: 1:1 (default), 16:9, 9:16,
  4:3, 3:4. Edit mode auto-activates when an input image is provided.
allowed-tools: Read, Bash
---

# Astraler Generate Image

Multi-provider image **generator AND editor** designed to be called from agent
harnesses (Obsidian Agent Client, Antigravity, Claude Code). The skill
**enhances the user's raw prompt** with a structured framework before calling
the image API, then returns a JSON line on stdout that the calling agent can
parse to render or attach the image.

**Two modes** — auto-detected from whether an input image is supplied:
- **Generate** (default): text → new image. v1.0+
- **Edit**: text + input image → modified image. v1.2+

**Providers:**
- **Google Gemini / Imagen 4** (default) — uses `GEMINI_API_KEY`
- **OpenAI GPT-image models** — uses `OPENAI_API_KEY`

## Trigger Phrases

> Only activate this skill when the user explicitly mentions **"Astraler"** in an image generation or editing context.

### Generate mode triggers

**Google / Gemini (default):** `"Astraler tạo ảnh"`, `"Astraler vẽ"`, `"dùng Astraler generate image"`, `"Astraler draw"`, `"Astraler image"`, `"tạo ảnh bằng Astraler"`, `"nhờ Astraler vẽ"`, `"Astraler vẽ cho tôi"`, `"dùng Astraler để vẽ"`, `"Astraler create image"`, `"astraler gemini"`, `"astraler imagen"`

**OpenAI / GPT-image:** `"astraler image gpt"`, `"astraler image openai"`, `"astraler gpt image"`, `"astraler openai"`, `"astraler dùng openai"`, `"astraler gpt-image"`, `"astraler image gpt-image-1"`, `"astraler chatgpt image"`, `"astraler vẽ bằng openai"`, `"astraler tạo ảnh openai"`

### Edit mode triggers (NEW in v1.2)

Edit mode activates when **two conditions** are both true:

1. The word **"Astraler"** appears
2. The user supplies (or refers to) an image **AND** uses an editing verb. Common signals:
   - **Vietnamese:** `"chỉnh"`, `"sửa"`, `"đổi"`, `"thay"`, `"thêm"`, `"xóa"`, `"biến thể"`, `"khác"`, `"chuyển"`, `"vẽ lại"`, `"theo phong cách"`, `"restyle"`
   - **English:** `"edit"`, `"modify"`, `"change"`, `"replace"`, `"add"`, `"remove"`, `"variant"`, `"restyle"`, `"in the style of"`, `"make it"`
   - **Image references:** `"ảnh này"`, `"ảnh vừa rồi"`, `"ảnh trên"`, `"the image above"`, `"this picture"`, `"that one"`

**Example edit triggers:**
- `"Astraler chỉnh ảnh này thành phong cách Studio Ghibli"` — restyle
- `"Astraler đổi background của ảnh trên sang bãi biển"` — background swap
- `"Astraler thêm một con đường mòn vào ảnh vừa rồi"` — add element
- `"Astraler restyle this photo as oil painting"` — style transfer
- `"Astraler image gpt edit ảnh này, xóa người bên trái"` — explicit OpenAI edit (with mask if needed)

**Where does the input image come from?**
- User attached/pasted an image in the harness — the harness provides a file path; pass it as `--input_image`
- User refers to a previously generated image — read `output_path` from the previous v1.x JSON output and pass it as `--input_image`
- User typed a path explicitly (rare)

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

**Env-var precedence:** values already exported in the harness's process environment (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `IMAGE_MODEL`) take priority over what's in `.env` — the `.env` only fills in keys that aren't already set. This lets a harness inject keys at runtime without editing the file.

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

### Step 4b — Edit mode (NEW in v1.2)

Activate **edit mode** by passing `--input_image <path>`. The script auto-detects mode from the presence of this flag — same script, same JSON contract, just a different code path.

**Gemini multimodal edit (recommended for restyle, scene change, free-form edits):**
```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "<your Preserve/Change/Constraint enhanced prompt>" \
  --enhanced_from "<user's raw edit request>" \
  --input_image "/path/to/source.png" \
  --output "edited.png" \
  --model "gemini-3-pro-image-preview"
```

**OpenAI image edit (no mask — text-driven full-image edit):**
```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "<your enhanced prompt>" \
  --enhanced_from "<raw>" \
  --input_image "/path/to/source.png" \
  --output "edited.png" \
  --model "gpt-image-1" \
  --quality "high"
```

**OpenAI inpainting (mask required — precise area edit):**
```bash
# mask.png: same dimensions as source.png; transparent pixels = areas to edit,
#           opaque pixels = preserve. Caller agent must produce this mask itself
#           (typically only useful when user explicitly draws/specifies a region).
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "remove the person on the left, fill with matching grass" \
  --input_image "/path/to/photo.png" \
  --mask "/path/to/mask.png" \
  --output "edited.png" \
  --model "gpt-image-1"
```

**Provider routing for edits:**

| Situation | Provider | Why |
|---|---|---|
| Restyle / phong cách / "vẽ lại" / "make it cyberpunk" | **Gemini** (default) | Best at preserving subject identity while changing style |
| Background swap / scene change | **Gemini** | Multimodal context handles spatial composition well |
| Adding / removing elements (no specific area) | **Gemini** | Free-form text-driven edits |
| Precise inpainting of a specific area | **OpenAI** + `--mask` | Only OpenAI accepts masks |
| User says "astraler image gpt edit" / "astraler openai edit" | **OpenAI** | Explicit user intent |

**Edit mode prompt enhancement framework — Preserve / Change / Constraint:**

This is **different** from the 7-component generate framework. Edit prompts must be *explicit about what stays and what changes* — otherwise the model often re-renders too much (changing things the user wanted preserved).

| Component | What to write | Example |
|---|---|---|
| **Preserve** | What MUST NOT change. Subject identity (face, pose, clothing if it's a portrait), composition, color palette, framing, specific elements user wants kept. | "Preserve the same lake, mountains, and composition exactly. Keep the cat's face and orange fur unchanged." |
| **Change** | What the user wants different. Be **very specific** — not "make it nicer" but concrete attributes (lighting, sky, single element, mood, style). | "Change ONLY the sky from clear blue to dramatic stormy thunderclouds. Add lightning strikes in the distance." |
| **Constraint** | Technical constraints. Aspect ratio, dimensions, "no text", "no watermark", "match original lighting direction". | "Maintain the original 16:9 aspect ratio. Match the original camera angle." |

**Critical pattern:** start the prompt with the user's intent in **plain language**, then explicitly enumerate Preserve/Change. Models reward this structure heavily — vague edits like "make it more dramatic" produce hit-or-miss results.

**Don't over-enhance:**
- If the user already wrote a detailed edit prompt, leave it.
- If the user says "minor adjustment" / "subtle" / "nhẹ", reflect that in the Change section ("subtle warm tone shift, NOT a full color regrade").
- Per-provider tweaks: **Gemini** handles Vietnamese natively in edit mode too — no need to translate. **OpenAI** prefers structured English with explicit Preserve/Change labels.

### Step 5 — Parse the JSON line and report

The last stdout line is always JSON. Parse it and report:
- File path — **always read this from `output_path` in the JSON, not the `--output` flag you passed**. Some Google models (e.g. `gemini-3-pro-image-preview`) return JPEG inline data even if the user requested `.png`; the script rewrites the extension to match the actual MIME so callers always get a valid file.
- Model used
- The enhanced prompt (so the user can iterate)
- Token usage (OpenAI only)

**Success shape (generate mode):**
```json
{
  "ok": true,
  "mode": "generate",
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
  "input_images": [],
  "mask": null,
  "usage": {"total_tokens": 1234, "input_tokens": 50, "output_tokens": 1184},
  "duration_ms": 8420
}
```

**Success shape (edit mode):** identical schema, with `mode: "edit"`, `input_images: ["/abs/path/to/source.png"]`, and `mask` set to the mask path or `null`.

**Failure shape:**
```json
{"ok": false, "error": "...", "provider": "openai", "model": "gpt-image-1"}
```

When `ok: true`, return the `output_path` to the caller so the harness can render the image. Offer to refine (different style, ratio, model — or in edit mode: tweak the Preserve/Change emphasis).

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

## Edit Mode Examples (NEW in v1.2)

These show the Preserve/Change/Constraint pattern. The user's input is short; the agent's job is to enumerate what to keep and what to change so the model doesn't drift.

### Example F — Restyle (most common edit case)

**User:** `"Astraler chỉnh ảnh con mèo này theo phong cách Studio Ghibli"` *(with attached cat photo at /tmp/cat.jpg)*

**Enhanced edit prompt:**
> Restyle this photograph as a hand-painted Studio Ghibli animation cel.
> **Preserve:** the same cat's pose, identity, and orientation; the same composition and framing; the spatial relationship to the wooden windowsill it's sitting on.
> **Change:** rendering style from photorealistic to soft watercolor with thick black outlines; lighting to dreamy warm golden tones typical of Ghibli films; background simplified to painterly bokeh.
> **Constraint:** maintain original aspect ratio. No text, no logos.

**Command:**
```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "<enhanced above>" --enhanced_from "Astraler chỉnh ảnh con mèo này theo phong cách Studio Ghibli" \
  --input_image "/tmp/cat.jpg" --output "cat_ghibli.png" \
  --model "gemini-3-pro-image-preview"
```

### Example G — Iterate on a previously generated image

**User:** *(after v1.x just generated /tmp/city.png)* `"Astraler chỉnh ảnh vừa rồi cho có nhiều xe bay hơn và ánh sáng ấm hơn"`

**Detection:** "ảnh vừa rồi" → use the `output_path` from the previous JSON output as `--input_image`.

**Enhanced:**
> Modify the cyberpunk city scene to feel busier and warmer.
> **Preserve:** the city skyline, building architecture, street layout, lone figure on the street, neon signage placement, overall composition.
> **Change:** add 3-4 more flying cars at varying altitudes streaking across the sky with motion-blur trails; shift the lighting palette from cool magenta-cyan to warmer amber-orange tones while keeping neon accents.
> **Constraint:** keep the same 16:9 framing.

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "<enhanced>" --enhanced_from "Astraler chỉnh ảnh vừa rồi cho có nhiều xe bay hơn và ánh sáng ấm hơn" \
  --input_image "/tmp/city.png" --output "city_v2.png" \
  --model "gemini-3-pro-image-preview"
```

### Example H — Background swap

**User:** `"Astraler đổi background ảnh sản phẩm này sang bãi biển hoàng hôn"` *(attached: product photo of a watch)*

**Enhanced:**
> Replace the background of this product photograph while keeping the product perfectly intact.
> **Preserve:** the watch — exact shape, materials, dial, hands, every reflection on the glass and metal, and its position/angle in the frame. Do NOT alter the product in any way.
> **Change:** the background from plain white studio to a sunset beach — soft golden hour light, gentle ocean waves, blurred out-of-focus background; ground plane should imply soft sand.
> **Constraint:** lighting on the watch must match the new warm sunset direction (subtle warm fill from camera-left). Same aspect ratio. No additional objects.

### Example I — Add element with spatial guidance

**User:** `"Astraler thêm một con đường mòn dẫn vào rừng trong ảnh phong cảnh này"` *(attached: forest landscape)*

**Enhanced:**
> Add a winding dirt walking path leading into the forest from the foreground.
> **Preserve:** the forest itself — every tree, the canopy lighting, the ground texture outside the path, the sky, the overall composition and atmosphere.
> **Change:** carve a natural-looking dirt path roughly 1m wide that starts at the bottom-center of the frame and curves into the trees toward the back-right. Path should have visible footprints/wear, scattered leaves, and small stones at the edges. The grass around it should look slightly trampled at the borders.
> **Constraint:** path should look photorealistic and physically plausible (correct perspective, scale, lighting consistent with existing scene). Same aspect ratio.

### Example J — OpenAI inpainting (mask-based, precise edit)

**User:** `"astraler image gpt edit ảnh này, xóa người ngồi bên trái"` *(attached: photo, plus user/agent has produced a mask file with transparent area over the unwanted person)*

**Enhanced (OpenAI prefers shorter labeled structure for inpainting):**
> Subject: empty wooden bench in a park.
> Style: photorealistic, match source.
> Lighting: match source — afternoon natural light from upper-left.
> Negative: no person, no figure, no shadow of a person.

```bash
python3 "$SKILL_DIR/scripts/generate.py" \
  --prompt "<enhanced>" --enhanced_from "astraler image gpt edit ảnh này, xóa người ngồi bên trái" \
  --input_image "/tmp/photo.png" --mask "/tmp/photo_mask.png" \
  --output "photo_edited.png" --model "gpt-image-1" --quality "high"
```

> **Note on masks:** unless the user explicitly says where to edit AND the harness has a way to produce a mask file (rare), prefer text-driven Gemini edits over mask-based inpainting. Mask creation is friction the user typically can't do from inside Obsidian/Antigravity.

---

## Model Reference

### OpenAI GPT-image

| Model | Quality | Speed | Notes |
|-------|---------|-------|-------|
| `gpt-image-1` | ⭐⭐⭐⭐⭐ | Medium | **Default**, stable & recommended ✅ |
| `gpt-image-1.5` | ⭐⭐⭐⭐⭐ | Medium | Higher-quality variant |
| `gpt-image-1-mini` | ⭐⭐⭐ | Fast | Cheaper, good for drafts — use shorter prompts |
| `gpt-image-2` | ⭐⭐⭐⭐⭐ | Medium | Requires org verification ⚠️ |

Sizes (OpenAI does **not** natively support 4:3 / 3:4 — the closest landscape/portrait size is substituted):
- `1:1` → `1024x1024`
- `16:9` → `1536x1024` (landscape) · `4:3` → `1536x1024` (substituted)
- `9:16` → `1024x1536` (portrait) · `3:4` → `1024x1536` (substituted)

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
