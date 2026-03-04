param(
    [Parameter(Mandatory = $true)]
    [string]$FolderPath,

    [Parameter(Mandatory = $false)]
    [string]$OutputDir = "",

    [switch]$Recursive,
    [switch]$SmartSegment,
    [switch]$ProTranslate,
    [switch]$BilingualAss,
    [switch]$BurnIn
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $FolderPath)) {
    throw "Folder not found: $FolderPath"
}

if (-not $PSCommandPath) {
    throw "PSCommandPath is not available."
}

$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $PSCommandPath) "..\\..")).Path
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Missing venv. Run: .\\setup.ps1 -Target Agent1"
}

$tool = Join-Path $repoRoot "agents\\agent1-video-subtitle\\tools\\studio_cli.py"
if (-not (Test-Path -LiteralPath $tool)) {
    throw "Tool not found: $tool"
}

if ($OutputDir) {
    if (-not [IO.Path]::IsPathRooted($OutputDir)) {
        $OutputDir = Join-Path $repoRoot $OutputDir
    }
    if (-not (Test-Path -LiteralPath $OutputDir)) {
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    }
    $OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
}

$argsList = @("--input", $FolderPath, "--transcribe")
if ($OutputDir) { $argsList += @("--output-dir", $OutputDir) }
if ($Recursive) { $argsList += "--recursive" }
if ($SmartSegment) { $argsList += "--smart-segment" }
if ($ProTranslate) { $argsList += "--pro-translate" }
if ($BilingualAss) { $argsList += "--bilingual-ass" }
if ($BurnIn) { $argsList += "--burn-in" }
if (-not $BilingualAss) { $argsList += "--ass" }

& $venvPython $tool @argsList

