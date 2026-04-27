# CLAUDE.md — astraler-generate-image-skill

A standalone Python CLI skill for **generating AND editing** images via Google
Gemini/Imagen and OpenAI GPT-image, designed to be invoked from AI agent
harnesses (Claude Code, Antigravity, Obsidian Agent Client). The agent reads
`SKILL.md` for the trigger description and prompt-enhancement framework, then
runs `scripts/generate.py`. Two modes — auto-detected from `--input_image`:
**generate** (text → image) and **edit** (text + image → modified image).

> If the parent `my-skills/CLAUDE.md` is also loaded (i.e. you're working
> inside the monorepo), it has additional shared conventions. This file is
> self-contained for the standalone-clone case.

## Trigger

The skill activates ONLY when the user mentions **"Astraler"** in an image
generation context. Generic image requests use the harness's built-in tool or
a different skill (e.g. `google-generate-image`). Don't change this behavior
without checking with the user — it's intentional to avoid spamming.

## Distribution

- Distributed via **skills CLI from GitHub**, NOT npm:
  `npx skills add thientranhung/astraler-generate-image-skill`
- `package.json` has `"private": true` — do NOT run `npm publish`. The
  registry is not used.
- Versioned via git tags + GitHub Releases. After merging a release PR:
  `git tag -a vX.Y.Z -m "..."` → `git push origin vX.Y.Z` →
  `gh release create vX.Y.Z`

## Constraints

- **Python stdlib only** — no `pip install`, no `requirements.txt`.
  HTTP via `urllib.request`. The `--help` and `--json` modes are intentionally
  zero-dependency so the skill installs via plain copy.
- **Python 3.8+ compat** — use `Optional[str]` from `typing`, NOT `str | None`
  (PEP 604) syntax. The `from __future__ import annotations` is present.
- **JSON output contract** — `scripts/generate.py` must always emit exactly
  one final single-line JSON on stdout (success OR failure, even via `fail()`).
  Callers parse this. Don't add extra trailing prints. Decorative banner is OK
  but goes ABOVE the JSON line; `--json` / `--quiet` suppresses it.
- **Honor response MIME** — Gemini 3 returns JPEG inline data even when the
  user requested a `.png` file. The script reads `inlineData.mimeType` and
  rewrites the output extension. Callers MUST read the actual file path from
  `output_path` in the JSON, not assume it equals `--output`.
- **API keys go in headers, never URL query** — `x-goog-api-key` for Google,
  `Authorization: Bearer` for OpenAI. Keys in URLs leak into error messages,
  server logs, and HTTP referrers.
- **Validate `--model`** before URL interpolation — `^[A-Za-z0-9._-]+$`. Pass
  `safe=''` to `urllib.parse.quote`.
- **Edit mode** activates when `--input_image` is provided. Routing rules:
  Gemini multimodal (`gemini-*`) for free-form edits; OpenAI `/v1/images/edits`
  (multipart) when `--mask` is given. Imagen `:predict` does NOT accept image
  input — `edit_google` rejects non-Gemini models early.
- **Edit prompts** use a different framework than generate: **Preserve / Change /
  Constraint** (explicit about what stays vs changes). Models drift if the user's
  raw "make it cyberpunk" goes through unenhanced. See SKILL.md examples F-J.
- **Input image limit**: 18 MB (`MAX_INPUT_BYTES`). Above this, fail before
  network. Caller agent should resize/compress upstream if needed.

## File Map

- `SKILL.md` — trigger description + 7-component prompt enhancement framework
  (Subject / Composition / Style / Lighting / Mood / Technical / Negative) +
  before/after examples. Read by the agent when the skill activates.
- `scripts/generate.py` — the actual CLI. Stdlib only. ~400 lines.
- `references/models.md` — detailed model specs, endpoints, payload formats.
  Read by the agent only when the user asks specifics.
- `.env` (gitignored) / `.env.example` — API keys. The script auto-discovers
  `.env` across 7 fallback paths (see `candidate_env_paths` in
  `scripts/generate.py`); harness env vars take precedence over the file.
- `package.json` — for `skills` CLI metadata, NOT npm publish.
- `install.sh` / `uninstall.sh` — used by the `skills` CLI during install.

## Smoke Test

End-to-end tests (~5-30s each, real API call — need `GEMINI_API_KEY` in `.env`):

**Generate mode:**
```bash
python3 scripts/generate.py \
  --prompt "a red apple on a wooden table, photorealistic, soft window light" \
  --output /tmp/test.png --json
```

**Edit mode (uses output of the generate test as input):**
```bash
python3 scripts/generate.py \
  --prompt "Restyle as Studio Ghibli watercolor. Preserve apple shape and table. Change rendering style only." \
  --input_image /tmp/test.png \
  --output /tmp/test_ghibli.png \
  --model gemini-3-pro-image-preview --json
```

Verify: stdout last line has `"ok": true`, `mode: "generate"` or `"edit"`, file at `output_path` opens.
Note: the file extension may differ from `--output` (e.g. `.jpg` instead of
`.png`) if the model returned JPEG.

## Workflow for Changes

1. Feature branch (`feat/...` for new behavior, `chore/...`, `fix/...`,
   `docs/...` as appropriate)
2. Run `/simplify` before commit — refactor + remove dead code
3. Add specific files only — NEVER `git add -A` (your `.env` with real API
   keys is in the working tree)
4. Push, `gh pr create`
5. Run `/review <PR#>` for an independent second opinion
6. Address review findings in a second commit on the same branch
7. Squash merge with `gh pr merge <N> --squash --delete-branch`
8. Sync local: `git checkout main && git pull --ff-only && git branch -d <branch>`
9. Tag + Release: `git tag -a vX.Y.Z` → `git push origin vX.Y.Z` →
   `gh release create vX.Y.Z`
