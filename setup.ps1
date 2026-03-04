param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("Agent1", "Agent1Realtime", "Agent2", "All")]
    [string]$Target = "All",

    [Parameter(Mandatory = $false)]
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSVersion.Major -lt 5) {
    throw "PowerShell 5.1+ is required. Current: $($PSVersionTable.PSVersion)"
}

if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Warning "PowerShell 7+ is recommended. Current: $($PSVersionTable.PSVersion). Running in compatibility mode."
}

function Get-PythonExe {
    param([string]$Requested)

    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested)) {
            throw "PythonExe not found: $Requested"
        }
        return $Requested
    }

    # Prefer a direct executable path (works with & invocation).
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Path) {
        return $python.Path
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py -and $py.Path) {
        return $py.Path
    }

    throw "Python not found. Install Python or ensure `py`/`python` is on PATH."
}

function New-Venv {
    param(
        [string]$Python,
        [string]$VenvDir
    )

    if (-not (Test-Path -LiteralPath $VenvDir)) {
        Write-Host "Creating venv: $VenvDir"
        & $Python -m venv $VenvDir
    }

    $venvPython = Join-Path $VenvDir "Scripts\\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "Venv python not found: $venvPython"
    }

    return $venvPython
}

function Test-PythonVersion {
    param([string]$Python)

    $versionText = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if (-not $versionText) {
        throw "Unable to detect Python version from: $Python"
    }

    $version = [version]$versionText
    if ($version -lt [version]"3.8") {
        throw "Python 3.8+ is required. Current: $version"
    }
}

function Install-Req {
    param(
        [string]$VenvPython,
        [string]$RequirementsPath
    )

    if (-not (Test-Path -LiteralPath $RequirementsPath)) {
        return
    }

    Write-Host "Upgrading pip..."
    & $VenvPython -m pip install --upgrade pip

    Write-Host "Installing: $RequirementsPath"
    & $VenvPython -m pip install -r $RequirementsPath
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$python = Get-PythonExe -Requested $PythonExe
Test-PythonVersion -Python $python
$venvDir = Join-Path $repoRoot ".venv"
$venvPython = New-Venv -Python $python -VenvDir $venvDir

switch ($Target) {
    "Agent1" {
        Install-Req -VenvPython $venvPython -RequirementsPath (Join-Path $repoRoot "agents\\agent1-video-subtitle\\requirements.txt")
    }
    "Agent1Realtime" {
        Install-Req -VenvPython $venvPython -RequirementsPath (Join-Path $repoRoot "agents\\agent1-video-subtitle\\requirements.txt")
        Install-Req -VenvPython $venvPython -RequirementsPath (Join-Path $repoRoot "agents\\agent1-video-subtitle\\requirements-realtime.txt")
    }
    "Agent2" {
        Install-Req -VenvPython $venvPython -RequirementsPath (Join-Path $repoRoot "agents\\agent2-doc-excel\\requirements.txt")
    }
    "All" {
        Install-Req -VenvPython $venvPython -RequirementsPath (Join-Path $repoRoot "agents\\agent1-video-subtitle\\requirements.txt")
        Install-Req -VenvPython $venvPython -RequirementsPath (Join-Path $repoRoot "agents\\agent2-doc-excel\\requirements.txt")
    }
}

Write-Host "OK. Venv: $venvDir"
