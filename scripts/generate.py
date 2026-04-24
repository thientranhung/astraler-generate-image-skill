#!/usr/bin/env python3
"""
Astraler Generate Image — Multi-provider image generation script.

Supported providers:
  - Google Gemini / Imagen  (GEMINI_API_KEY)
  - OpenAI GPT-image models (OPENAI_API_KEY)

Usage:
  python3 generate.py --prompt "..." --output "out.png" [--model gpt-image-1] [--aspect_ratio 16:9] [--quality high] [--provider openai]
"""

import urllib.request
import urllib.parse
import json
import base64
import os
import sys
import argparse

# ─── Size mapping for aspect ratios ───────────────────────────────────────────
# OpenAI GPT-image models support: 1024x1024, 1536x1024 (landscape), 1024x1536 (portrait), auto
OPENAI_SIZE_MAP = {
    "1:1":  "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "4:3":  "1536x1024",   # closest landscape
    "3:4":  "1024x1536",   # closest portrait
    "auto": "auto",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, val = line.split('=', 1)
                        os.environ[key.strip()] = val.strip().strip("'\"")


def detect_provider(model_name: str) -> str:
    """Auto-detect provider from model name."""
    if model_name.startswith("gpt-image"):
        return "openai"
    if model_name.startswith("dall-e"):
        return "openai"
    if model_name == "gpt-image-2":
        return "openai"
    return "google"  # gemini-* or imagen-*


def resolve_output_ext(output_file: str, output_format: str) -> str:
    """Ensure output file has the correct extension."""
    base, _ = os.path.splitext(output_file)
    ext = output_format if output_format != "jpeg" else "jpg"
    return f"{base}.{ext}"


# ─── OpenAI provider ──────────────────────────────────────────────────────────

def generate_openai(prompt: str, output_file: str, model_name: str,
                    aspect_ratio: str, quality: str, output_format: str):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set. Configure it in .env or export it.", file=sys.stderr)
        print("  Get a key at: https://platform.openai.com/api-keys", file=sys.stderr)
        sys.exit(1)

    size = OPENAI_SIZE_MAP.get(aspect_ratio, "auto")
    payload = {
        "model": model_name,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "output_format": output_format,
    }

    url = "https://api.openai.com/v1/images/generations"
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))

        images = result.get("data", [])
        if not images:
            print("Error: No images returned from OpenAI.", file=sys.stderr)
            print(json.dumps(result, indent=2), file=sys.stderr)
            sys.exit(1)

        b64_image = images[0].get("b64_json")
        if not b64_image:
            # DALL-E 2/3 may return URL instead
            img_url = images[0].get("url")
            if img_url:
                with urllib.request.urlopen(img_url) as r:
                    image_data = r.read()
            else:
                print("Error: No image bytes or URL returned.", file=sys.stderr)
                sys.exit(1)
        else:
            image_data = base64.b64decode(b64_image)

        output_file = resolve_output_ext(output_file, output_format)
        with open(output_file, "wb") as f:
            f.write(image_data)

        usage = result.get("usage", {})
        print(f"✅ Image saved → {output_file}")
        print(f"   Model : {model_name}  |  Size: {size}  |  Quality: {quality}")
        if usage:
            print(f"   Tokens: {usage.get('total_tokens', '?')} total "
                  f"({usage.get('input_tokens','?')} in / {usage.get('output_tokens','?')} out)")

    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        print(f"HTTP Error {e.code}: {error_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ─── Google Gemini / Imagen provider ─────────────────────────────────────────

def generate_google(prompt: str, output_file: str, model_name: str, aspect_ratio: str):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set.", file=sys.stderr)
        print("  Get a free key at: https://aistudio.google.com/app/apikey", file=sys.stderr)
        sys.exit(1)

    encoded_model = urllib.parse.quote(model_name)
    is_gemini_model = model_name.startswith("gemini")

    if is_gemini_model:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{encoded_model}:generateContent?key={api_key}")
        payload = {
            "contents": [
                {"parts": [{"text": prompt + f" (Aspect ratio: {aspect_ratio})"}]}
            ]
        }
    else:
        # Imagen models use :predict endpoint
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{encoded_model}:predict?key={api_key}")
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect_ratio,
                "outputOptions": {"mimeType": "image/png"},
            },
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))

        b64_image = None
        if is_gemini_model:
            candidates = result.get("candidates", [])
            if not candidates:
                print("Error: No candidates returned.", file=sys.stderr)
                print(json.dumps(result, indent=2), file=sys.stderr)
                sys.exit(1)
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts or "inlineData" not in parts[0]:
                print("Error: No inlineData returned.", file=sys.stderr)
                print(json.dumps(result, indent=2), file=sys.stderr)
                sys.exit(1)
            b64_image = parts[0]["inlineData"].get("data")
        else:
            predictions = result.get("predictions", [])
            if not predictions:
                print("Error: No predictions returned.", file=sys.stderr)
                print(json.dumps(result, indent=2), file=sys.stderr)
                sys.exit(1)
            b64_image = (predictions[0].get("bytesBase64Encoded")
                         or predictions[0].get("bytesBase64"))

        if not b64_image:
            print("Error: No image bytes returned.", file=sys.stderr)
            sys.exit(1)

        image_data = base64.b64decode(b64_image)
        with open(output_file, "wb") as f:
            f.write(image_data)

        print(f"✅ Image saved → {output_file}")
        print(f"   Model : {model_name}  |  Aspect ratio: {aspect_ratio}")

    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        print(f"HTTP Error {e.code}: {error_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ─── Main entry point ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Astraler Generate Image — Google Gemini/Imagen & OpenAI GPT-image"
    )
    parser.add_argument("--prompt",       required=True, help="Text prompt for the image")
    parser.add_argument("--output",       required=True, help="Output filename (e.g. out.png)")
    parser.add_argument("--model",        help="Model name (overrides .env IMAGE_MODEL)")
    parser.add_argument("--aspect_ratio", default="1:1",
                        help="Aspect ratio: 1:1 | 16:9 | 9:16 | 4:3 | 3:4 (Google) or auto (OpenAI)")
    parser.add_argument("--provider",     choices=["google", "openai", "auto"], default="auto",
                        help="Provider: google | openai | auto (auto-detect from model name)")
    parser.add_argument("--quality",      default="auto",
                        choices=["auto", "low", "medium", "high", "standard", "hd"],
                        help="Image quality (OpenAI GPT-image: low/medium/high; DALL-E 3: hd/standard)")
    parser.add_argument("--format",       default="png",
                        choices=["png", "jpeg", "webp"],
                        help="Output format for OpenAI GPT-image models (default: png)")

    args = parser.parse_args()
    load_env()

    # Resolve model
    # Resolve model — default depends on provider hint in trigger
    model_name = args.model or os.environ.get("IMAGE_MODEL", "gemini-3-pro-image-preview")

    # Resolve provider
    provider = args.provider
    if provider == "auto":
        provider = detect_provider(model_name)

    print(f"🎨 Astraler Generate Image")
    print(f"   Provider : {provider.upper()}")
    print(f"   Model    : {model_name}")
    print(f"   Prompt   : {args.prompt[:80]}{'...' if len(args.prompt) > 80 else ''}")
    print()

    if provider == "openai":
        generate_openai(
            prompt=args.prompt,
            output_file=args.output,
            model_name=model_name,
            aspect_ratio=args.aspect_ratio,
            quality=args.quality,
            output_format=args.format,
        )
    else:
        generate_google(
            prompt=args.prompt,
            output_file=args.output,
            model_name=model_name,
            aspect_ratio=args.aspect_ratio,
        )


if __name__ == "__main__":
    main()
