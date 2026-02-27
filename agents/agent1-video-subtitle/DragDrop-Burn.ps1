param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$InputPath,

    [Parameter(Mandatory = $false)]
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $PSCommandPath) {
    throw "PSCommandPath is not available; cannot resolve repo root."
}

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "Input not found: $InputPath"
}

$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $PSCommandPath) "..\\..")).Path
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Missing venv. Run: .\\setup.ps1 -Target Agent1Realtime (or Agent1) first."
}

$args = @(
    "--input", $InputPath,
    "--transcribe",
    "--smart-segment",
    "--pro-translate",
    "--bilingual-ass",
    "--burn-in"
)
if ($OutputDir) {
    $args = @("--output-dir", $OutputDir) + $args
}

& $venvPython ".\\agents\\agent1-video-subtitle\\tools\\studio_cli.py" @args
