param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("Agent1", "Agent1Realtime", "Agent2", "All")]
    [string]$Target = "All",

    [Parameter(Mandatory = $false)]
    [string]$PythonExe = "",

    [Parameter(Mandatory = $false)]
    [switch]$SkipFfmpeg,

    [Parameter(Mandatory = $false)]
    [switch]$SkipEnv,

    [Parameter(Mandatory = $false)]
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = "Stop"

if (-not $PSCommandPath) {
    throw "PSCommandPath is not available; cannot resolve repo root."
}

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

function Write-Step {
    param([string]$Message)
    Write-Host "[STEP] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Warning $Message
}

function Test-CommandExists {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    return ($null -ne $cmd)
}

function Assert-PowerShellCompatibility {
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        throw "PowerShell 5.1+ is required. Current: $($PSVersionTable.PSVersion)"
    }

    if ($PSVersionTable.PSVersion.Major -lt 7) {
        Write-Warn "Detected Windows PowerShell $($PSVersionTable.PSVersion). PowerShell 7+ is recommended."
    } else {
        Write-Ok "Detected PowerShell $($PSVersionTable.PSVersion)"
    }
}

function Ensure-DotEnvFiles {
    param([string]$RepoRoot)

    $examplePath = Join-Path $RepoRoot ".env.example"
    $envPath = Join-Path $RepoRoot ".env"

    $exampleContent = @(
        "# Local environment variables for Helper",
        "# Keep secrets out of source control.",
        "# For Copilot CLI fallback token mode (optional):",
        "COPILOT_GITHUB_TOKEN=",
        "GH_TOKEN=",
        "GITHUB_TOKEN=",
        ""
    ) -join [Environment]::NewLine

    if (-not (Test-Path -LiteralPath $examplePath)) {
        Set-Content -LiteralPath $examplePath -Value $exampleContent -Encoding UTF8
        Write-Ok "Created .env.example"
    }

    if (-not (Test-Path -LiteralPath $envPath)) {
        Set-Content -LiteralPath $envPath -Value $exampleContent -Encoding UTF8
        Write-Ok "Created .env placeholder"
    } else {
        Write-Ok ".env already exists"
    }
}

function Install-FfmpegBestEffort {
    if (Test-CommandExists -Name "ffmpeg") {
        Write-Ok "FFmpeg already installed"
        return
    }

    Write-Step "FFmpeg not found. Trying automatic installation..."

    $installed = $false

    if (Test-CommandExists -Name "winget") {
        try {
            & winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -eq 0 -and (Test-CommandExists -Name "ffmpeg")) {
                $installed = $true
                Write-Ok "FFmpeg installed via winget"
            }
        } catch {
            Write-Warn "winget installation failed: $($_.Exception.Message)"
        }
    }

    if (-not $installed -and (Test-CommandExists -Name "choco")) {
        try {
            & choco install ffmpeg -y
            if ($LASTEXITCODE -eq 0 -and (Test-CommandExists -Name "ffmpeg")) {
                $installed = $true
                Write-Ok "FFmpeg installed via Chocolatey"
            }
        } catch {
            Write-Warn "Chocolatey installation failed: $($_.Exception.Message)"
        }
    }

    if (-not $installed) {
        Write-Warn "Unable to install FFmpeg automatically. Please install it manually and ensure 'ffmpeg' is on PATH."
    }
}

function Invoke-Setup {
    param(
        [string]$RepoRoot,
        [string]$SetupTarget,
        [string]$Python
    )

    $setupScript = Join-Path $RepoRoot "setup.ps1"
    if (-not (Test-Path -LiteralPath $setupScript)) {
        throw "Missing setup script: $setupScript"
    }

    Write-Step "Installing Python dependencies via setup.ps1 (Target=$SetupTarget)"

    if ($Python) {
        & $setupScript -Target $SetupTarget -PythonExe $Python
    } else {
        & $setupScript -Target $SetupTarget
    }

    Write-Ok "Dependencies installation completed"
}

function Invoke-SmokeTests {
    param(
        [string]$RepoRoot,
        [string]$SetupTarget
    )

    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "Missing venv python: $venvPython"
    }

    Write-Step "Running smoke tests"

    if ($SetupTarget -in @("Agent1", "Agent1Realtime", "All")) {
        & $venvPython -c "import srt, opencc; print('agent1-python-ok')"
        if ($LASTEXITCODE -ne 0) { throw "Agent1 smoke test failed" }
        Write-Ok "Agent1 smoke test passed"
    }

    if ($SetupTarget -in @("Agent1Realtime")) {
        & $venvPython -c "import faster_whisper, sounddevice, numpy; print('agent1-realtime-python-ok')"
        if ($LASTEXITCODE -ne 0) { throw "Agent1Realtime smoke test failed" }
        Write-Ok "Agent1Realtime smoke test passed"
    }

    if ($SetupTarget -in @("Agent2", "All")) {
        & $venvPython -c "import pandas, openpyxl; print('agent2-python-ok')"
        if ($LASTEXITCODE -ne 0) { throw "Agent2 smoke test failed" }
        Write-Ok "Agent2 smoke test passed"
    }
}

Set-Location -LiteralPath $repoRoot

Write-Step "Starting local deployment (Target=$Target)"
Assert-PowerShellCompatibility

if (-not $SkipEnv) {
    Write-Step "Ensuring .env and .env.example"
    Ensure-DotEnvFiles -RepoRoot $repoRoot
}

if (-not $SkipFfmpeg) {
    Install-FfmpegBestEffort
}

Invoke-Setup -RepoRoot $repoRoot -SetupTarget $Target -Python $PythonExe

if (-not $SkipSmokeTest) {
    Invoke-SmokeTests -RepoRoot $repoRoot -SetupTarget $Target
}

Write-Host "" 
Write-Ok "Local deployment completed"
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1) Agent1: .\agent-hub.ps1 -Agent agent1 -Task video.subtitles.generate -InputPath <video-file>"
Write-Host "  2) Agent2: .\agent-hub.ps1 -Agent agent2 -Task excel.summarize -InputPath <excel-file>"
Write-Host "  3) Pro translate (optional): gh copilot -- login"
