#!/usr/bin/env python3
"""
Astraler Generate Image — Multi-provider image generation + editing script.

Supported providers:
  - Google Gemini / Imagen  (GEMINI_API_KEY)
  - OpenAI GPT-image models (OPENAI_API_KEY)

Modes:
  - generate (default): text → image
  - edit:               text + input image → modified image
                        (auto-activated when --input_image is provided)

Usage:
  # Generate
  python3 generate.py --prompt "..." --output "out.png" [--model gpt-image-1]

  # Edit (preserve subject, change style/lighting/elements)
  python3 generate.py --prompt "..." --input_image "in.png" --output "out.png"

  # Edit with mask (OpenAI inpainting — transparent areas in mask = edit zone)
  python3 generate.py --prompt "..." --input_image "in.png" --mask "mask.png" \\
      --output "out.png" --model "gpt-image-1"

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
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, NoReturn, Optional, Tuple

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

# Network timeout (seconds) — image generation typically takes 5-30s; cap at 90s
# to prevent the agent harness from hanging indefinitely on a stalled connection.
HTTP_TIMEOUT = 90

# Whitelist of characters allowed in a model name. Prevents URL path-injection
# (e.g. "foo/../bar") since the model is interpolated into the API URL.
_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Soft cap on input image size — Gemini's request limit is ~20 MB total, and
# OpenAI's edits endpoint accepts up to 25 MB. Above this we error out before
# making the network call.
MAX_INPUT_BYTES = 18 * 1024 * 1024  # 18 MB

# Image MIMEs both Gemini and OpenAI accept as input. Gates what `load_image`
# will pass through — `mimetypes.guess_type` may resolve other formats (heic,
# avif) that the APIs don't accept, so we explicitly allow only this set.
_SUPPORTED_INPUT_MIMES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


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


def _parse_env_line(line: str):
    """Parse one .env line into (key, value) or return None.

    Handles common shell-style .env conventions:
      - Leading `export ` prefix (so users can `source` the file too)
      - Quoted values: 'foo' or "foo"
      - Inline comments after an UNQUOTED value: KEY=value  # note
        (Comments inside quotes are preserved verbatim.)
    """
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    if line.startswith("export "):
        line = line[len("export "):].lstrip()
    key, val = line.split("=", 1)
    key = key.strip()
    val = val.strip()
    if val.startswith(("'", '"')) and len(val) >= 2 and val[0] == val[-1]:
        val = val[1:-1]
    elif "#" in val:
        val = val.split("#", 1)[0].rstrip()
    return key, val


def load_env(explicit: Optional[str] = None) -> Optional[str]:
    """Load .env into os.environ; return path used (or None).

    Values already set in os.environ are NOT overwritten — the harness's env
    takes precedence over the .env file. Document this in SKILL.md.
    """
    for p in candidate_env_paths(explicit):
        if p and os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    parsed = _parse_env_line(line)
                    if parsed is None:
                        continue
                    key, val = parsed
                    if key not in os.environ:
                        os.environ[key] = val
            return p
    return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def detect_provider(model_name: str) -> str:
    """Auto-detect provider from model name."""
    if model_name.lower().startswith("gpt-image"):
        return "openai"
    return "google"


def validate_model_name(model: str) -> None:
    """Raise SystemExit if the model name contains characters unsafe for URL interpolation."""
    if not _MODEL_NAME_RE.match(model):
        # Not using fail() here because we don't have json_only/quiet context yet.
        print(json.dumps({
            "ok": False,
            "error": f"Invalid model name {model!r}: must match {_MODEL_NAME_RE.pattern}",
        }), file=sys.stdout)
        sys.exit(1)


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


def load_image(path: str) -> Tuple[bytes, str]:
    """Read an image file and return (raw_bytes, mime_type).

    Raises ValueError on missing file, unsupported format, or oversize input.
    Format is inferred from the file extension via `mimetypes.guess_type`; we
    don't sniff magic bytes because both target APIs accept the MIME we send
    and validate server-side.
    """
    if not os.path.isfile(path):
        raise ValueError(f"input image not found: {path}")
    size = os.path.getsize(path)
    if size > MAX_INPUT_BYTES:
        raise ValueError(
            f"input image is {size:,} bytes; max is {MAX_INPUT_BYTES:,} "
            f"(~{MAX_INPUT_BYTES // (1024 * 1024)} MB)"
        )
    mime, _ = mimetypes.guess_type(path)
    if mime not in _SUPPORTED_INPUT_MIMES:
        ext = os.path.splitext(path)[1].lower()
        raise ValueError(
            f"unsupported input image extension {ext!r}; "
            f"supported MIME types: {', '.join(sorted(_SUPPORTED_INPUT_MIMES))}"
        )
    with open(path, "rb") as f:
        return f.read(), mime


def _extract_gemini_inline(result: dict) -> Tuple[Optional[str], Optional[str]]:
    """Extract (b64_image, mime_type) from a Gemini :generateContent response.

    Returns (None, None) if no inlineData part is present (e.g. model returned
    a text-only refusal, or an unexpected response shape).
    """
    for cand in result.get("candidates") or []:
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData")
            if inline:
                return inline.get("data"), inline.get("mimeType")
    return None, None


def _gemini_refusal_reason(result: dict) -> Optional[str]:
    """Surface why Gemini didn't produce an image, if it told us.

    Common causes: safety blocks (`promptFeedback.blockReason`), early stop
    (`candidates[0].finishReason != STOP`), or a text-only refusal in the
    parts array. Returns None if the response shape gives no hint and the
    caller should fall back to a generic error.
    """
    pf = result.get("promptFeedback") or {}
    if pf.get("blockReason"):
        return f"Gemini refused (promptFeedback): {pf['blockReason']}"
    cands = result.get("candidates") or []
    if cands:
        finish = cands[0].get("finishReason")
        if finish and finish != "STOP":
            return f"Gemini stopped early (finishReason): {finish}"
        # Text-only response: model spoke instead of drawing.
        for part in cands[0].get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                return f"Gemini returned text instead of an image: {text[:200]}"
    return None


def _decode_and_write(b64: str, output: str, ext: Optional[str]) -> Tuple[str, bytes]:
    """Decode a base64 image and write it to `output`, rewriting extension to `ext`.

    Returns (final_path_on_disk, decoded_bytes). When ext is None or matches
    the requested extension, the path is unchanged.
    """
    image_data = base64.b64decode(b64)
    final_path = replace_ext(output, ext)
    with open(final_path, "wb") as f:
        f.write(image_data)
    return final_path, image_data


def _multipart_encode(fields: Dict[str, str],
                      files: Dict[str, Tuple[str, bytes, str]]) -> Tuple[bytes, str]:
    """Encode form fields + file parts as multipart/form-data.

    `files` is {field_name: (filename, raw_bytes, content_type)}.
    Returns (body_bytes, content_type_header) — needed because OpenAI's
    /v1/images/edits endpoint accepts ONLY multipart, not JSON.
    """
    boundary = secrets.token_hex(16)
    sep = f"--{boundary}".encode()
    end = f"--{boundary}--".encode()
    body = bytearray()
    for key, value in fields.items():
        body += sep + b"\r\n"
        body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
        body += str(value).encode("utf-8") + b"\r\n"
    for key, (filename, data, content_type) in files.items():
        body += sep + b"\r\n"
        body += (f'Content-Disposition: form-data; name="{key}"; '
                 f'filename="{filename}"\r\n').encode("utf-8")
        body += f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
        body += data + b"\r\n"
    body += end + b"\r\n"
    return bytes(body), f"multipart/form-data; boundary={boundary}"


# ─── Output helpers ───────────────────────────────────────────────────────────

def _build_result(args, *, mode: str, provider: str, output_path: str,
                  mime: str, bytes_size: int, started: float, **extras) -> dict:
    """Build the success-result dict with the uniform fields callers expect.

    Provider-specific fields (quality, format, size, usage) are passed via
    **extras to override defaults. Keeps the JSON contract symmetric across
    generate/edit and across providers — every key listed below is present
    in EVERY result, so callers never have to branch on optional keys.
    """
    return {
        "ok": True,
        "mode": mode,
        "provider": provider,
        "model": args.model,
        "output_path": os.path.abspath(output_path),
        "aspect_ratio": args.aspect_ratio,
        "mime": mime,
        "bytes_size": bytes_size,
        "prompt": args.prompt,
        "enhanced_from": args.enhanced_from,
        "input_images": [os.path.abspath(args.input_image)] if args.input_image else [],
        "mask": os.path.abspath(args.mask) if args.mask else None,
        "duration_ms": int((time.time() - started) * 1000),
        # Defaults below — provider-specific callers override via **extras.
        # All four keys are always present in the JSON output so callers can
        # safely do result["quality"] without a KeyError on Google results.
        "size": None,
        "quality": None,
        "format": None,
        "usage": None,
        **extras,
    }


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

def _redact(text: str) -> str:
    """Strip API keys / bearer tokens from error messages before they hit JSON output."""
    # Google AI Studio key style: AIza... (39 chars). Bearer tokens / OpenAI sk-...
    text = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "AIza***REDACTED***", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{16,}", "sk-***REDACTED***", text)
    text = re.sub(r"[?&]key=[^&\s\"']+", "?key=***REDACTED***", text)
    return text


def post_json(url: str, payload: dict, *, headers: Optional[dict] = None,
              provider: str, model: str, json_only: bool, quiet: bool) -> dict:
    """POST JSON payload, return parsed response. Calls fail() (which exits) on any error."""
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    return _do_post(url, body, req_headers,
                    provider=provider, model=model,
                    json_only=json_only, quiet=quiet)


def post_multipart(url: str, fields: Dict[str, str],
                   files: Dict[str, Tuple[str, bytes, str]], *,
                   headers: Optional[dict] = None,
                   provider: str, model: str,
                   json_only: bool, quiet: bool) -> dict:
    """POST multipart/form-data, return parsed JSON response."""
    body, ct = _multipart_encode(fields, files)
    req_headers = {"Content-Type": ct, **(headers or {})}
    return _do_post(url, body, req_headers,
                    provider=provider, model=model,
                    json_only=json_only, quiet=quiet)


def _do_post(url: str, body: bytes, headers: dict, *,
             provider: str, model: str, json_only: bool, quiet: bool) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        fail(f"{provider.title()} HTTP {e.code}: {_redact(err_body)}",
             json_only=json_only, quiet=quiet, provider=provider, model=model)
    except Exception as e:  # noqa: BLE001 — any failure surfaces to JSON
        fail(f"{provider.title()} request failed: {_redact(str(e))}",
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

    output_ext = "jpg" if args.format == "jpeg" else args.format
    b64_image = images[0].get("b64_json")
    if b64_image:
        output_file, image_data = _decode_and_write(b64_image, args.output, output_ext)
    else:
        # /v1/images/generations may return a URL when b64_json isn't requested;
        # /v1/images/edits never does, so this branch is generations-only.
        img_url = images[0].get("url")
        if not img_url:
            fail("OpenAI returned no image bytes or URL.",
                 json_only=json_only, quiet=quiet,
                 provider="openai", model=args.model)
        with urllib.request.urlopen(img_url, timeout=HTTP_TIMEOUT) as r:
            image_data = r.read()
        output_file = replace_ext(args.output, output_ext)
        with open(output_file, "wb") as f:
            f.write(image_data)

    return _build_result(
        args, mode="generate", provider="openai",
        output_path=output_file,
        mime=f"image/{args.format}",
        bytes_size=len(image_data),
        started=started,
        size=size, quality=args.quality, format=args.format,
        usage=result.get("usage"),
    )


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

    # safe='' — don't preserve any path separators in the model name.
    encoded_model = urllib.parse.quote(args.model, safe="")
    is_gemini = args.model.startswith("gemini")
    method = "generateContent" if is_gemini else "predict"
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{encoded_model}:{method}")

    if is_gemini:
        # Gemini image-preview models read aspect ratio from prompt text.
        payload = {
            "contents": [
                {"parts": [{"text": f"{args.prompt} (Aspect ratio: {args.aspect_ratio})"}]}
            ]
        }
    else:
        # Imagen models use :predict with a different payload shape.
        payload = {
            "instances": [{"prompt": args.prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": args.aspect_ratio,
                "outputOptions": {"mimeType": "image/png"},
            },
        }

    started = time.time()
    # Pass API key in header, not URL. Keeps it out of error messages, server
    # logs, and HTTP referrers.
    result = post_json(
        url, payload,
        headers={"x-goog-api-key": api_key},
        provider="google", model=args.model,
        json_only=json_only, quiet=quiet,
    )

    if is_gemini:
        b64_image, response_mime = _extract_gemini_inline(result)
    else:
        predictions = result.get("predictions") or []
        b64_image = response_mime = None
        if predictions:
            b64_image = (predictions[0].get("bytesBase64Encoded")
                         or predictions[0].get("bytesBase64"))
            response_mime = predictions[0].get("mimeType") or "image/png"

    if not b64_image:
        msg = _gemini_refusal_reason(result) if is_gemini else None
        fail(msg or "Google returned no image bytes.",
             json_only=json_only, quiet=quiet,
             provider="google", model=args.model, raw=result)

    # Honor the actual MIME from the API response — Gemini 3 returns JPEG inline
    # data even when the user asks for a .png file. Rewrite the extension so the
    # file on disk matches its bytes.
    final_mime = response_mime or "image/png"
    final_path, image_data = _decode_and_write(b64_image, args.output, ext_for_mime(final_mime))

    return _build_result(
        args, mode="generate", provider="google",
        output_path=final_path,
        mime=final_mime,
        bytes_size=len(image_data),
        started=started,
    )


# ─── Edit mode — Google Gemini multimodal ────────────────────────────────────

def edit_google(args, *, json_only: bool, quiet: bool) -> dict:
    """Edit an existing image using Gemini multimodal (text + image input)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        fail(
            "GEMINI_API_KEY not set. Get a free key at "
            "https://aistudio.google.com/app/apikey and configure it in .env.",
            json_only=json_only, quiet=quiet,
            provider="google", model=args.model,
        )

    if not args.model.startswith("gemini"):
        fail(
            f"Edit mode on Google requires a Gemini multimodal model "
            f"(got {args.model!r}). Imagen :predict does not accept image input.",
            json_only=json_only, quiet=quiet,
            provider="google", model=args.model,
        )

    try:
        img_bytes, img_mime = load_image(args.input_image)
    except ValueError as e:
        fail(str(e), json_only=json_only, quiet=quiet,
             provider="google", model=args.model)

    encoded_model = urllib.parse.quote(args.model, safe="")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{encoded_model}:generateContent")

    # Order matters in the parts array: text first, then inlineData. Gemini's
    # documented edit-prompt convention treats this as "apply text to image".
    payload = {
        "contents": [{
            "parts": [
                {"text": args.prompt},
                {"inlineData": {
                    "mimeType": img_mime,
                    "data": base64.b64encode(img_bytes).decode("ascii"),
                }},
            ]
        }]
    }

    started = time.time()
    result = post_json(
        url, payload,
        headers={"x-goog-api-key": api_key},
        provider="google", model=args.model,
        json_only=json_only, quiet=quiet,
    )

    b64_image, response_mime = _extract_gemini_inline(result)
    if not b64_image:
        fail(_gemini_refusal_reason(result)
             or "Google returned no image bytes (model may have refused).",
             json_only=json_only, quiet=quiet,
             provider="google", model=args.model, raw=result)

    final_mime = response_mime or "image/png"
    final_path, image_data = _decode_and_write(b64_image, args.output, ext_for_mime(final_mime))

    return _build_result(
        args, mode="edit", provider="google",
        output_path=final_path,
        mime=final_mime,
        bytes_size=len(image_data),
        started=started,
    )


# ─── Edit mode — OpenAI /v1/images/edits ─────────────────────────────────────

def edit_openai(args, *, json_only: bool, quiet: bool) -> dict:
    """Edit an existing image using OpenAI's /v1/images/edits endpoint.

    Supports optional mask: PNG with transparent (alpha=0) areas marking
    the region to edit. Without a mask, the model edits the whole image
    according to the prompt.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        fail(
            "OPENAI_API_KEY not set. Get a key at https://platform.openai.com/api-keys "
            "and configure it in .env.",
            json_only=json_only, quiet=quiet,
            provider="openai", model=args.model,
        )

    try:
        img_bytes, img_mime = load_image(args.input_image)
    except ValueError as e:
        fail(str(e), json_only=json_only, quiet=quiet,
             provider="openai", model=args.model)

    # Use synthetic ASCII filenames in the multipart body. OpenAI routes parts
    # by the `name=` field ("image" / "mask"), not by `filename=`, so the user's
    # actual filename is purely informational. Synthesizing it eliminates the
    # multipart-header injection class entirely (a real filename containing `"`
    # or CRLF — legal on POSIX — would break the multipart frame).
    files: Dict[str, Tuple[str, bytes, str]] = {
        "image": (f"image.{ext_for_mime(img_mime) or 'png'}", img_bytes, img_mime),
    }
    if args.mask:
        try:
            mask_bytes, mask_mime = load_image(args.mask)
        except ValueError as e:
            fail(f"mask: {e}", json_only=json_only, quiet=quiet,
                 provider="openai", model=args.model)
        files["mask"] = (f"mask.{ext_for_mime(mask_mime) or 'png'}", mask_bytes, mask_mime)

    size = OPENAI_SIZE_MAP.get(args.aspect_ratio, "auto")
    fields: Dict[str, str] = {
        "model": args.model,
        "prompt": args.prompt,
        "n": "1",
        "size": size,
        "quality": args.quality,
        "output_format": args.format,
    }
    if args.background and args.background != "auto":
        fields["background"] = args.background

    started = time.time()
    result = post_multipart(
        "https://api.openai.com/v1/images/edits",
        fields, files,
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
    if not b64_image:
        # Surface the API's own error if it included one — `result["error"]`
        # is OpenAI's documented error envelope shape.
        api_err = (result.get("error") or {}).get("message") if isinstance(result, dict) else None
        msg = "OpenAI edit returned no image bytes (b64_json missing)."
        if api_err:
            msg += f" API: {api_err}"
        fail(msg, json_only=json_only, quiet=quiet,
             provider="openai", model=args.model, raw=result)

    output_ext = "jpg" if args.format == "jpeg" else args.format
    output_file, image_data = _decode_and_write(b64_image, args.output, output_ext)

    return _build_result(
        args, mode="edit", provider="openai",
        output_path=output_file,
        mime=f"image/{args.format}",
        bytes_size=len(image_data),
        started=started,
        size=size, quality=args.quality, format=args.format,
        usage=result.get("usage"),
    )


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
                        choices=["auto", "low", "medium", "high"],
                        help="OpenAI GPT-image quality (low | medium | high | auto)")
    parser.add_argument("--format", default="png", choices=["png", "jpeg", "webp"],
                        help="Output format for OpenAI GPT-image (default: png)")
    parser.add_argument("--background", default="auto",
                        choices=["auto", "transparent", "opaque"],
                        help="OpenAI GPT-image background (transparent requires png/webp)")
    parser.add_argument("--enhanced_from",
                        help="Original raw user prompt before enhancement (for traceability)")
    parser.add_argument("--input_image",
                        help="Path to input image — activates EDIT mode (modify this image per prompt)")
    parser.add_argument("--mask",
                        help="Path to mask PNG (transparent areas = edit zone). OpenAI only.")
    parser.add_argument("--env_file", help="Explicit path to .env file")
    parser.add_argument("--json", action="store_true",
                        help="Emit only the final JSON line; suppress decorative output")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress decorative output (still emits JSON line)")

    args = parser.parse_args()

    env_used = load_env(args.env_file)

    args.model = args.model or os.environ.get("IMAGE_MODEL", DEFAULT_MODEL)
    validate_model_name(args.model)

    # Mode = edit if user supplied an input image, otherwise generate.
    mode = "edit" if args.input_image else "generate"

    # --mask only makes sense with edit mode; reject early if used standalone.
    if args.mask and mode != "edit":
        fail("--mask requires --input_image (edit mode only).",
             json_only=args.json, quiet=args.quiet or args.json,
             provider="-", model=args.model)

    provider = args.provider if args.provider != "auto" else detect_provider(args.model)

    # Mask is OpenAI-only. Reject incompatible combinations clearly instead of
    # silently overriding the provider — if the model is a Gemini one, OpenAI
    # would reject it server-side with an opaque 400. Caller must use a GPT-image
    # model when supplying a mask.
    if args.mask and provider != "openai":
        fail(
            "--mask is OpenAI-only (Gemini multimodal does not accept inpainting masks). "
            f"Got provider={provider!r}, model={args.model!r}. "
            "Use a gpt-image-* model (e.g. --model gpt-image-1) when supplying --mask.",
            json_only=args.json, quiet=args.quiet or args.json,
            provider=provider, model=args.model,
        )

    json_only = args.json
    quiet = args.quiet or json_only

    if not quiet:
        print("🎨 Astraler Generate Image")
        print(f"   Mode     : {mode.upper()}")
        print(f"   Provider : {provider.upper()}")
        print(f"   Model    : {args.model}")
        if env_used:
            print(f"   Env file : {env_used}")
        if mode == "edit":
            print(f"   Input    : {args.input_image}")
            if args.mask:
                print(f"   Mask     : {args.mask}")
        prompt_preview = args.prompt[:80] + ("..." if len(args.prompt) > 80 else "")
        print(f"   Prompt   : {prompt_preview}")
        print()

    if mode == "edit":
        if provider == "openai":
            result = edit_openai(args, json_only=json_only, quiet=quiet)
        else:
            result = edit_google(args, json_only=json_only, quiet=quiet)
    else:
        if provider == "openai":
            result = generate_openai(args, json_only=json_only, quiet=quiet)
        else:
            result = generate_google(args, json_only=json_only, quiet=quiet)

    emit(result, json_only=json_only, quiet=quiet)


if __name__ == "__main__":
    main()
