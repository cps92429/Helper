param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("excel.summarize", "excel.automanage")]
    [string]$Task,

    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $false)]
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $PSCommandPath) {
    throw "PSCommandPath is not available; cannot resolve repo root."
}
$scriptDir = Split-Path -Parent $PSCommandPath

function Resolve-RepoRoot {
    param([string]$ScriptDir)
    return (Resolve-Path (Join-Path $ScriptDir "..\\..")).Path
}

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

if (-not (Test-Path -LiteralPath $InputPath)) { throw "InputPath not found: $InputPath" }

$repoRoot = Resolve-RepoRoot -ScriptDir $scriptDir
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Missing venv. Run: .\\setup.ps1 -Target Agent2"
}

if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "Output"
}
Ensure-Dir -Path $OutputDir

$scriptPath = Join-Path $repoRoot "agents\\agent2-doc-excel\\tools\\excel_agent.py"
& $venvPython $scriptPath --task $Task --input $InputPath --output-dir $OutputDir
