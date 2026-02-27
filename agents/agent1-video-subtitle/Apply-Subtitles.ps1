param(
    [Parameter(Mandatory = $true)]
    [string]$VideoPath,

    [Parameter(Mandatory = $true)]
    [string]$SubtitlePath,

    [Parameter(Mandatory = $false)]
    [ValidateSet("burn", "mux")]
    [string]$Mode = "burn",

    [Parameter(Mandatory = $false)]
    [string]$OutputPath = ""
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

function Get-Agent1Config {
    param([string]$RepoRoot)
    $path = Join-Path $RepoRoot "agents\\agent1-video-subtitle\\agent1.config.json"
    return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json)
}

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

if (-not (Test-Path -LiteralPath $VideoPath)) { throw "Video not found: $VideoPath" }
if (-not (Test-Path -LiteralPath $SubtitlePath)) { throw "Subtitles not found: $SubtitlePath" }

$repoRoot = Resolve-RepoRoot -ScriptDir $scriptDir
$config = Get-Agent1Config -RepoRoot $repoRoot
$ffmpeg = $config.ffmpeg.ffmpeg_exe
if (-not $ffmpeg) { $ffmpeg = "ffmpeg" }

$outDir = Join-Path $repoRoot $config.defaults.output_dir_name
Ensure-Dir -Path $outDir

if (-not $OutputPath) {
    $base = [IO.Path]::GetFileNameWithoutExtension($VideoPath)
    $OutputPath = Join-Path $outDir ($base + ".subtitled.mp4")
}

if ($Mode -eq "burn") {
    $ext = [IO.Path]::GetExtension($SubtitlePath).ToLowerInvariant()
    if ($ext -eq ".ass") {
        & $ffmpeg -y -i $VideoPath -vf "ass=$SubtitlePath" -c:a copy $OutputPath
    } else {
        & $ffmpeg -y -i $VideoPath -vf "subtitles=$SubtitlePath" -c:a copy $OutputPath
    }
} else {
    & $ffmpeg -y -i $VideoPath -i $SubtitlePath -c copy -c:s mov_text $OutputPath
}

Write-Host "OK: $OutputPath"
