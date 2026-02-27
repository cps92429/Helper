param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("agent1", "agent2")]
    [string]$Agent,

    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "video.translate",
        "video.subtitles.generate",
        "video.subtitles.design",
        "video.subtitles.preview",
        "video.apply",
        "video.ui",
        "subtitles.translate.pro",
        "excel.summarize",
        "excel.automanage"
    )]
    [string]$Task,

    [Parameter(Mandatory = $false)]
    [string]$InputPath = "",

    [Parameter(Mandatory = $false)]
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

switch ($Agent) {
    "agent1" {
        & (Join-Path $repoRoot "agents\\agent1-video-subtitle\\Invoke-Agent1.ps1") -Task $Task -InputPath $InputPath -OutputDir $OutputDir
    }
    "agent2" {
        & (Join-Path $repoRoot "agents\\agent2-doc-excel\\Invoke-Agent2.ps1") -Task $Task -InputPath $InputPath -OutputDir $OutputDir
    }
}
