# Astraler Generate Image — Model Reference

Detailed specs for each model the skill supports. The agent reads this only
when a user asks something specific (pricing, endpoint shape, prompt style)
that isn't in `SKILL.md`.

## Table of Contents

- [Quick comparison](#quick-comparison)
- [Google models](#google-models)
  - [Imagen 4](#imagen-4--imagen-40-generate-001)
  - [Imagen 4 Fast](#imagen-4-fast--imagen-40-fast-generate-001)
  - [Gemini 3 Pro Image Preview](#gemini-3-pro-image-preview)
  - [Gemini 3.1 Flash Image Preview](#gemini-31-flash-image-preview)
- [OpenAI models](#openai-models)
  - [gpt-image-1](#gpt-image-1)
  - [gpt-image-1.5](#gpt-image-15)
  - [gpt-image-1-mini](#gpt-image-1-mini)
  - [gpt-image-2](#gpt-image-2)
- [Aspect ratios](#aspect-ratios)
- [API key setup](#api-key-setup)

---

## Quick comparison

| Model | Provider | Endpoint | Multilingual | Vector/Logo | Photoreal | Speed | Notes |
|---|---|---|---|---|---|---|---|
| `gemini-3-pro-image-preview` | Google | `:generateContent` | ✅ Excellent | Good | Excellent | Med | Default. Reads Vietnamese natively |
| `gemini-3.1-flash-image-preview` | Google | `:generateContent` | ✅ Good | Good | Very good | Fast | Cheaper, faster |
| `imagen-4.0-generate-001` | Google | `:predict` | EN preferred | Good | ⭐ Best | Med | Highest technical quality |
| `imagen-4.0-fast-generate-001` | Google | `:predict` | EN preferred | Good | Excellent | Fast | Imagen 4 Fast |
| `gpt-image-1` | OpenAI | `/v1/images/generations` | ✅ Good | ⭐ Excellent | Excellent | Med | OpenAI default |
| `gpt-image-1.5` | OpenAI | `/v1/images/generations` | ✅ Good | Excellent | ⭐ Best | Med | Higher quality |
| `gpt-image-1-mini` | OpenAI | `/v1/images/generations` | OK | Good | Good | ⭐ Fast | Cheap drafts |
| `gpt-image-2` | OpenAI | `/v1/images/generations` | ✅ Good | Excellent | Excellent | Med | Requires org verification |

---

## Google models

All Google models live under `https://generativelanguage.googleapis.com/v1beta/models/<MODEL>:<METHOD>?key=<GEMINI_API_KEY>`.

### Imagen 4 — `imagen-4.0-generate-001`

- **Method:** `predict`
- **Best for:** product shots, commercial photography, sharp technical detail, anything that needs to look "professional"
- **Prompt style:** flowing English sentences. Avoid keyword spam.
- **Aspect ratios:** native parameter — passed in payload, not as text in prompt.

**Payload:**
```json
{
  "instances": [{"prompt": "your prompt"}],
  "parameters": {
    "sampleCount": 1,
    "aspectRatio": "16:9",
    "outputOptions": {"mimeType": "image/png"}
  }
}
```

### Imagen 4 Fast — `imagen-4.0-fast-generate-001`

- Same shape as Imagen 4. Faster, lower cost, slightly less detail.
- Use for drafts, ideation, batch generation.

### Gemini 3 Pro Image Preview

- **Method:** `generateContent`
- **Best for:** anything where the user wrote the prompt in Vietnamese — handles Vietnamese (and other languages) natively without needing translation. Good general-purpose default.
- **Prompt style:** natural, conversational. Aspect ratio is conveyed inline as `(Aspect ratio: 16:9)` appended to the prompt — the script does this automatically.

**Payload:**
```json
{
  "contents": [
    {"parts": [{"text": "your prompt (Aspect ratio: 16:9)"}]}
  ]
}
```

Response contains image as base64 in `candidates[0].content.parts[*].inlineData.data`.

### Gemini 3.1 Flash Image Preview

- Same shape as Gemini 3 Pro. Faster, slightly less polished output.

---

## OpenAI models

All OpenAI image models use `POST https://api.openai.com/v1/images/generations` with header `Authorization: Bearer $OPENAI_API_KEY`.

### gpt-image-1

- **Default OpenAI model.** Stable, widely available.
- **Best for:** logos, vector-style designs, illustrations, structured commercial work, text rendering inside images.
- **Prompt style:** structured, comma-separated phrases. Labeled sections (`Subject:`, `Style:`, `Lighting:`, `Composition:`) work very well.
- **Sizes:** `1024x1024` | `1536x1024` | `1024x1536` | `auto`
- **Quality:** `low` | `medium` | `high` | `auto`
- **Format:** `png` | `jpeg` | `webp`
- **Background:** `auto` | `transparent` | `opaque` (transparent requires png/webp)
- **Response:** always base64 (`data[0].b64_json`).

**Payload:**
```json
{
  "model": "gpt-image-1",
  "prompt": "your prompt",
  "n": 1,
  "size": "1536x1024",
  "quality": "high",
  "output_format": "png",
  "background": "auto"
}
```

### gpt-image-1.5

- Same API as `gpt-image-1`. Higher photoreal quality, slightly slower, slightly more expensive.
- Use for hero images, marketing visuals, anything where perceived quality matters.

### gpt-image-1-mini

- Same API as `gpt-image-1`. Smaller model — much cheaper, much faster.
- **Important:** keep prompts shorter (top 3-4 components of the framework). Long prompts cause the small model to lose track and produce inconsistent results.
- Best for: drafts, ideation, A/B testing prompt variants before committing to a full-quality generation.

### gpt-image-2

- Latest. Requires **organization verification** on the OpenAI platform — most accounts don't have access yet. The script will return an HTTP 403 / 400 error if your org isn't approved.
- If access is denied, fall back to `gpt-image-1.5` (closest in quality).

---

## Aspect ratios

| Ratio | OpenAI size | Use case |
|---|---|---|
| `1:1` | `1024x1024` | Square — Instagram post, avatar, logo |
| `16:9` | `1536x1024` | Widescreen — banner, wallpaper, YouTube thumbnail |
| `9:16` | `1024x1536` | Portrait — Story, TikTok, mobile |
| `4:3` | `1536x1024`* | Classic — presentation, blog header |
| `3:4` | `1024x1536`* | Tall portrait |

\* OpenAI doesn't natively support 4:3 / 3:4 — the closest landscape/portrait size is used instead.

Google models accept the ratio directly: `1:1`, `16:9`, `9:16`, `4:3`, `3:4` — Imagen as a payload parameter, Gemini as text appended to the prompt.

---

## API key setup

### Google (free tier available)

1. Visit https://aistudio.google.com/app/apikey
2. Sign in with a Google account
3. Click **"Create API key"**
4. Copy into `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```

Free quota covers a generous number of generations per day. See https://ai.google.dev/pricing for current limits.

### OpenAI

1. Visit https://platform.openai.com/api-keys
2. Click **"Create new secret key"**
3. Copy into `.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```

OpenAI is paid only — no free tier. GPT-image pricing is per-image, with quality tier multipliers. See https://openai.com/api/pricing/ for current rates.

For `gpt-image-2` access you need org verification — request via the OpenAI platform settings.
