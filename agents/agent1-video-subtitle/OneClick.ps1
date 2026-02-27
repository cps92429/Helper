param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$MediaPath,

    [Parameter(Mandatory = $false)]
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $MediaPath)) {
    throw "Media not found: $MediaPath"
}

if (-not $PSCommandPath) {
    throw "PSCommandPath is not available; cannot resolve repo root."
}

$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $PSCommandPath) "..\\..")).Path
Set-Location $repoRoot

if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "Output"
}
if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

Write-Host "1/3 生成字幕..." -ForegroundColor Cyan
& (Join-Path $repoRoot "agents\\agent1-video-subtitle\\Invoke-Agent1.ps1") -Task "video.subtitles.generate" -InputPath $MediaPath -OutputDir $OutputDir

$base = [IO.Path]::GetFileNameWithoutExtension($MediaPath)
$srt = Join-Path $OutputDir ($base + ".srt")

if (-not (Test-Path -LiteralPath $srt)) {
    # Best-effort fallback: pick the newest .srt in OutputDir.
    $candidate = Get-ChildItem -LiteralPath $OutputDir -Filter "*.srt" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($candidate) {
        $srt = $candidate.FullName
    }
}

if (-not (Test-Path -LiteralPath $srt)) {
    throw "SRT not found in OutputDir: $OutputDir"
}

Write-Host "2/3 字幕設計 (SRT -> ASS)..." -ForegroundColor Cyan
& (Join-Path $repoRoot "agents\\agent1-video-subtitle\\Invoke-Agent1.ps1") -Task "video.subtitles.design" -InputPath $srt -OutputDir $OutputDir

Write-Host "3/3 預覽字幕..." -ForegroundColor Cyan
& (Join-Path $repoRoot "agents\\agent1-video-subtitle\\Invoke-Agent1.ps1") -Task "video.subtitles.preview" -InputPath $srt -OutputDir $OutputDir

Write-Host "OK" -ForegroundColor Green

