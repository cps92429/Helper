# Helper Repository Guidelines

This repository is a Windows scripting toolbox, optimized for PowerShell-first workflows.

## Structure
- Put runnable scripts in `scripts/` when possible.
- Keep generated artifacts in `Output/`, `source/`, or `subtitles/` (do not mix outputs into the repo root).

## PowerShell Style
- Use 4-space indentation.
- Prefer explicit `param(...)` blocks and strict input validation.
- Use Verb-Noun function naming (for example, `Get-Thing`, `Invoke-Task`).
- Avoid destructive operations by default; require confirmation or a `-Force` switch.

## Python (Optional)
- Use 4-space indentation.
- Keep helpers small and CLI-friendly.

## Dev Notes
- Target Windows PowerShell 5.1 and/or PowerShell 7+; be explicit in docs when a script requires one.
- When execution policy blocks scripts, use process-only bypass:
  `Set-ExecutionPolicy -Scope Process Bypass`.

