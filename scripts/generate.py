#!/usr/bin/env python3
"""
Astraler Generate Image — Multi-provider image generation script.

Supported providers:
  - Google Gemini / Imagen  (GEMINI_API_KEY)
  - OpenAI GPT-image models (OPENAI_API_KEY)

Usage:
  python3 generate.py --prompt "..." --output "out.png" \
      [--model gpt-image-1] [--aspect_ratio 16:9] [--quality high] \
      [--provider openai] [--enhanced_from "raw user prompt"] [--json]

Designed to be called from agent harnesses (Obsidian Agent Client, Antigravity,
Claude Code). The final stdout line is always a single-line JSON object
describing the result, so callers can parse it deterministically.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import List, NoReturn, Optional

# ─── Constants ────────────────────────────────────────────────────────────────

# OpenAI GPT-image models support: 1024x1024, 1536x1024, 1024x1536, auto
OPENAI_SIZE_MAP = {
    "1:1":  "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "4:3":  "1536x1024",   # closest landscape
    "3:4":  "1024x1536",   # closest portrait
    "auto": "auto",
}

DEFAULT_MODEL = "gemini-3-pro-image-preview"


# ─── Env / path resolution ────────────────────────────────────────────────────

def candidate_env_paths(explicit: Optional[str]) -> List[str]:
    """Return ordered list of .env paths to try.

    Resolution order (first existing wins):
      1. --env_file CLI flag (if given)
      2. $ASTRALER_SKILL_DIR/.env  (set by harness)
      3. <script_dir>/../.env       (skill root, normal install)
      4. $HOME/.claude/skills/astraler-generate-image/.env
      5. $HOME/.gemini/antigravity/skills/astraler-generate-image/.env
      6. $HOME/.agents/skills/astraler-generate-image/.env
      7. ./.env                     (project-level)
    """
    paths: List[str] = []
    if explicit:
        paths.append(explicit)

    skill_dir_env = os.environ.get("ASTRALER_SKILL_DIR")
    if skill_dir_env:
        paths.append(os.path.join(skill_dir_env, ".env"))

    here = os.path.dirname(os.path.abspath(__file__))
    paths.append(os.path.normpath(os.path.join(here, "..", ".env")))

    home = os.path.expanduser("~")
    paths.extend([
        os.path.join(home, ".claude", "skills", "astraler-generate-image", ".env"),
        os.path.join(home, ".gemini", "antigravity", "skills", "astraler-generate-image", ".env"),
        os.path.join(home, ".agents", "skills", "astraler-generate-image", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ])
    return paths


def load_env(explicit: Optional[str] = None) -> Optional[str]:
    """Load .env into os.environ; return path used (or None)."""
    for p in candidate_env_paths(explicit):
        if p and os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    # Don't overwrite values already in env (harness may have set them).
                    key = key.strip()
                    if key not in os.environ:
                        os.environ[key] = val.strip().strip("'\"")
            return p
    return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def detect_provider(model_name: str) -> str:
    """Auto-detect provider from model name."""
    name = model_name.lower()
    if name.startswith("gpt-image") or name.startswith("dall-e"):
        return "openai"
    return "google"


def ext_for_mime(mime: Optional[str]) -> Optional[str]:
    """Return file extension for a MIME type (no leading dot). Normalizes jpe/jpeg → jpg."""
    if not mime:
        return None
    ext = mimetypes.guess_extension(mime.split(";")[0].strip())
    if not ext:
        return None
    ext = ext.lstrip(".").lower()
    return "jpg" if ext in ("jpe", "jpeg") else ext


def replace_ext(path: str, ext: Optional[str]) -> str:
    """Replace path's extension with `ext` (no leading dot). Returns unchanged if ext is None or already matches."""
    if not ext:
        return path
    base, current = os.path.splitext(path)
    if current.lstrip(".").lower() == ext.lower():
        return path
    return f"{base}.{ext}"


# ─── Output helpers ───────────────────────────────────────────────────────────

def emit(result: dict, *, json_only: bool, quiet: bool) -> None:
    """Print human-readable summary (unless quiet) and a final JSON line."""
    if not quiet and not json_only:
        ok = result.get("ok", False)
        marker = "✅" if ok else "❌"
        print(f"{marker} {'Image saved' if ok else 'Failed'} → {result.get('output_path', '-')}")
        meta_bits = [
            f"provider={result.get('provider')}",
            f"model={result.get('model')}",
            f"size={result.get('size') or result.get('aspect_ratio')}",
        ]
        if result.get("usage"):
            u = result["usage"]
            meta_bits.append(
                f"tokens={u.get('total_tokens', '?')} "
                f"({u.get('input_tokens','?')}in/{u.get('output_tokens','?')}out)"
            )
        print("   " + "  |  ".join(meta_bits))
        if result.get("enhanced_from"):
            print(f"   raw_prompt: {result['enhanced_from'][:100]}")
    # Always emit a single JSON line as the LAST stdout line so callers can parse.
    print(json.dumps(result, ensure_ascii=False))


def fail(msg: str, *, json_only: bool, quiet: bool, **extra) -> NoReturn:
    result = {"ok": False, "error": msg, **extra}
    emit(result, json_only=json_only, quiet=quiet)
    sys.exit(1)


# ─── HTTP helper ──────────────────────────────────────────────────────────────

def post_json(url: str, payload: dict, *, headers: Optional[dict] = None,
              provider: str, model: str, json_only: bool, quiet: bool) -> dict:
    """POST JSON payload, return parsed response. Calls fail() (which exits) on any error."""
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=req_headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        fail(f"{provider.title()} HTTP {e.code}: {err_body}",
             json_only=json_only, quiet=quiet, provider=provider, model=model)
    except Exception as e:  # noqa: BLE001 — any failure surfaces to JSON
        fail(f"{provider.title()} request failed: {e}",
             json_only=json_only, quiet=quiet, provider=provider, model=model)


# ─── OpenAI provider ──────────────────────────────────────────────────────────

def generate_openai(args, *, json_only: bool, quiet: bool) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        fail(
            "OPENAI_API_KEY not set. Get a key at https://platform.openai.com/api-keys "
            "and configure it in .env or ASTRALER_SKILL_DIR/.env.",
            json_only=json_only, quiet=quiet,
            provider="openai", model=args.model,
        )

    size = OPENAI_SIZE_MAP.get(args.aspect_ratio, "auto")
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "n": 1,
        "size": size,
        "quality": args.quality,
        "output_format": args.format,
    }
    if args.background and args.background != "auto":
        payload["background"] = args.background

    started = time.time()
    result = post_json(
        "https://api.openai.com/v1/images/generations",
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
        provider="openai", model=args.model,
        json_only=json_only, quiet=quiet,
    )

    images = result.get("data") or []
    if not images:
        fail("OpenAI returned no images.",
             json_only=json_only, quiet=quiet,
             provider="openai", model=args.model, raw=result)

    b64_image = images[0].get("b64_json")
    if b64_image:
        image_data = base64.b64decode(b64_image)
    else:
        img_url = images[0].get("url")
        if not img_url:
            fail("OpenAI returned no image bytes or URL.",
                 json_only=json_only, quiet=quiet,
                 provider="openai", model=args.model)
        with urllib.request.urlopen(img_url) as r:
            image_data = r.read()

    output_file = replace_ext(args.output, "jpg" if args.format == "jpeg" else args.format)
    with open(output_file, "wb") as f:
        f.write(image_data)

    return {
        "ok": True,
        "provider": "openai",
        "model": args.model,
        "output_path": os.path.abspath(output_file),
        "size": size,
        "aspect_ratio": args.aspect_ratio,
        "quality": args.quality,
        "format": args.format,
        "mime": f"image/{args.format}",
        "bytes_size": len(image_data),
        "prompt": args.prompt,
        "enhanced_from": args.enhanced_from,
        "usage": result.get("usage"),
        "duration_ms": int((time.time() - started) * 1000),
    }


# ─── Google Gemini / Imagen provider ─────────────────────────────────────────

def generate_google(args, *, json_only: bool, quiet: bool) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        fail(
            "GEMINI_API_KEY not set. Get a free key at "
            "https://aistudio.google.com/app/apikey and configure it in .env.",
            json_only=json_only, quiet=quiet,
            provider="google", model=args.model,
        )

    encoded_model = urllib.parse.quote(args.model)
    is_gemini = args.model.startswith("gemini")

    if is_gemini:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{encoded_model}:generateContent?key={api_key}")
        # Gemini image-preview models read aspect ratio from prompt text.
        payload = {
            "contents": [
                {"parts": [{"text": f"{args.prompt} (Aspect ratio: {args.aspect_ratio})"}]}
            ]
        }
    else:
        # Imagen models use the :predict endpoint with a different payload shape.
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{encoded_model}:predict?key={api_key}")
        payload = {
            "instances": [{"prompt": args.prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": args.aspect_ratio,
                "outputOptions": {"mimeType": "image/png"},
            },
        }

    started = time.time()
    result = post_json(
        url, payload,
        provider="google", model=args.model,
        json_only=json_only, quiet=quiet,
    )

    b64_image = None
    response_mime = None
    if is_gemini:
        candidates = result.get("candidates") or []
        if candidates:
            for part in candidates[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    b64_image = part["inlineData"].get("data")
                    response_mime = part["inlineData"].get("mimeType")
                    break
    else:
        predictions = result.get("predictions") or []
        if predictions:
            b64_image = (predictions[0].get("bytesBase64Encoded")
                         or predictions[0].get("bytesBase64"))
            response_mime = predictions[0].get("mimeType") or "image/png"

    if not b64_image:
        fail("Google returned no image bytes.",
             json_only=json_only, quiet=quiet,
             provider="google", model=args.model, raw=result)

    image_data = base64.b64decode(b64_image)

    # Honor the actual MIME from the API response — Gemini 3 returns JPEG inline
    # data even when the user asks for a .png file. Rewrite the extension so the
    # file on disk matches its bytes.
    final_mime = response_mime or "image/png"
    final_path = replace_ext(args.output, ext_for_mime(final_mime))

    with open(final_path, "wb") as f:
        f.write(image_data)

    return {
        "ok": True,
        "provider": "google",
        "model": args.model,
        "output_path": os.path.abspath(final_path),
        "aspect_ratio": args.aspect_ratio,
        "size": None,
        "mime": final_mime,
        "bytes_size": len(image_data),
        "prompt": args.prompt,
        "enhanced_from": args.enhanced_from,
        "usage": None,
        "duration_ms": int((time.time() - started) * 1000),
    }


# ─── Main entry point ─────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Astraler Generate Image — Google Gemini/Imagen & OpenAI GPT-image",
    )
    parser.add_argument("--prompt", required=True, help="Final (enhanced) text prompt for the image")
    parser.add_argument("--output", required=True, help="Output filename (e.g. out.png)")
    parser.add_argument("--model", help="Model name (overrides .env IMAGE_MODEL)")
    parser.add_argument("--aspect_ratio", default="1:1",
                        help="1:1 | 16:9 | 9:16 | 4:3 | 3:4 (Google) or auto (OpenAI)")
    parser.add_argument("--provider", choices=["google", "openai", "auto"], default="auto",
                        help="Provider hint; auto = infer from model name")
    parser.add_argument("--quality", default="auto",
                        choices=["auto", "low", "medium", "high", "standard", "hd"],
                        help="OpenAI GPT-image: low/medium/high; DALL-E 3: hd/standard")
    parser.add_argument("--format", default="png", choices=["png", "jpeg", "webp"],
                        help="Output format for OpenAI GPT-image (default: png)")
    parser.add_argument("--background", default="auto",
                        choices=["auto", "transparent", "opaque"],
                        help="OpenAI GPT-image background (transparent requires png/webp)")
    parser.add_argument("--enhanced_from",
                        help="Original raw user prompt before enhancement (for traceability)")
    parser.add_argument("--env_file", help="Explicit path to .env file")
    parser.add_argument("--json", action="store_true",
                        help="Emit only the final JSON line; suppress decorative output")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress decorative output (still emits JSON line)")

    args = parser.parse_args()

    env_used = load_env(args.env_file)

    args.model = args.model or os.environ.get("IMAGE_MODEL", DEFAULT_MODEL)
    provider = args.provider if args.provider != "auto" else detect_provider(args.model)

    json_only = args.json
    quiet = args.quiet or json_only

    if not quiet:
        print("🎨 Astraler Generate Image")
        print(f"   Provider : {provider.upper()}")
        print(f"   Model    : {args.model}")
        if env_used:
            print(f"   Env file : {env_used}")
        prompt_preview = args.prompt[:80] + ("..." if len(args.prompt) > 80 else "")
        print(f"   Prompt   : {prompt_preview}")
        print()

    if provider == "openai":
        result = generate_openai(args, json_only=json_only, quiet=quiet)
    else:
        result = generate_google(args, json_only=json_only, quiet=quiet)

    emit(result, json_only=json_only, quiet=quiet)


if __name__ == "__main__":
    main()
