# Copilot Instructions (Helper)

This repo is a Windows scripting toolbox (PowerShell-first). Optimize suggestions for Windows paths and PowerShell 7+, with compatibility notes for Windows PowerShell 5.1 when relevant.

## What to Generate
- Primary: `.ps1`, `.psm1`, `.psd1`, `.bat`
- Optional helpers: small `.py` utilities
- Documentation: concise `README.md` updates when behavior changes

## Coding Conventions
- PowerShell:
  - Use explicit `param()` blocks (do not rely on `$args`).
  - Use Verb-Noun function names.
  - Prefer clear errors: `throw` for fatal issues; `Write-Error`/`Write-Warning` for recoverable issues.
  - Prefer `-LiteralPath` when handling paths.
  - Avoid writing outside the repo unless the script is explicitly designed for it.
- Safety:
  - No destructive ops by default. If deletion/overwrite is required, add `-Force` and confirm intent.
  - Never print secrets (tokens, API keys) to console or logs.

## Output Policy
- Put generated artifacts under:
  - `Output/` (default)
  - `source/`
  - `subtitles/`
- Do not create or commit generated artifacts in the repo root.

## Logging
- Keep logs short and actionable.
- Prefer structured-ish logs: one line per major step; include paths and durations where useful.

## When Proposing Commands
- Use Windows-friendly commands and quoting.
- Prefer PowerShell examples; show `cmd.exe` only when needed.

