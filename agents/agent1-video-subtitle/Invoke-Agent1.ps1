param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "video.translate",
        "video.subtitles.generate",
        "video.subtitles.design",
        "video.subtitles.preview",
        "video.apply",
        "video.ui",
        "video.realtime.ui",
        "subtitles.translate.pro",
        "agent2.excel.summarize",
        "agent2.excel.automanage"
    )]
    [string]$Task,

    [Parameter(Mandatory = $false)]
    [string]$InputPath = "",

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

function Get-Agent1Config {
    param([string]$RepoRoot)

    $path = Join-Path $RepoRoot "agents\\agent1-video-subtitle\\agent1.config.json"
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing config: $path"
    }
    return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json)
}

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Escape-FfmpegFilterPath {
    param([string]$Path)
    # Escape for ffmpeg filter args like: -vf "ass='C\:/path/file.ass'"
    # - Use forward slashes to avoid backslash escaping hell
    # - Escape drive-colon to avoid option-separator parsing (C\:/...)
    $p = (Resolve-Path -LiteralPath $Path).Path
    $p = $p.Replace("\", "/")
    $p = $p -replace ":", "\:"
    $p = $p -replace "'", "\\'"
    return $p
}

function Get-DefaultOutputDir {
    param(
        [string]$RepoRoot,
        [object]$Config,
        [string]$Override
    )

    if ($Override) {
        # Allow specifying a new output directory that doesn't exist yet.
        Ensure-Dir -Path $Override
        return (Resolve-Path -LiteralPath $Override).Path
    }

    $out = Join-Path $RepoRoot $Config.defaults.output_dir_name
    Ensure-Dir -Path $out
    return $out
}

function Assert-InputPath {
    param([string]$Path)
    if (-not $Path) { throw "InputPath is required for this task." }
    if (-not (Test-Path -LiteralPath $Path)) { throw "InputPath not found: $Path" }
}

function Invoke-TurboTranscribe {
    param(
        [object]$Config,
        [string]$MediaPath,
        [string]$OutputDir,
        [switch]$Translate
    )

    $ps1 = $Config.transcription.turbo_transcribe_ps1
    if (-not (Test-Path -LiteralPath $ps1)) {
        throw "turbo-transcribe.ps1 not found: $ps1"
    }

    # Delegate to your existing workflow; output location is controlled by transcribe-config.ini.
    if ($Translate) {
        & $ps1 $MediaPath -OutputDir $OutputDir -Sentence -Progress -Translate
        return
    }

    & $ps1 $MediaPath -OutputDir $OutputDir -Sentence -Progress
}

function Invoke-FasterWhisperExe {
    param(
        [object]$Config,
        [string]$MediaPath,
        [string]$OutputDir,
        [string]$Model = "",
        [switch]$Translate
    )

    $exe = $Config.transcription.faster_whisper_exe
    if (-not $exe) {
        throw "faster_whisper_exe is not configured in agent1.config.json"
    }
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "faster-whisper-xxl.exe not found: $exe"
    }
    if (-not (Test-Path -LiteralPath $MediaPath)) {
        throw "Input not found: $MediaPath"
    }

    Ensure-Dir -Path $OutputDir

    if (-not $Model) {
        $Model = "turbo"
    }

    $args = @(
        $MediaPath,
        "-l", "zh",
        "-m", $Model,
        "-o", $OutputDir,
        "--sentence",
        "--standard_asia",
        "--print_progress",
        "--output_format", "srt", "vtt", "txt"
    )
    if ($Translate) { $args += @("--task", "translate") }

    & $exe @args
    if ($LASTEXITCODE -ne 0) {
        throw "faster-whisper-xxl.exe failed with exit code: $LASTEXITCODE"
    }
}

function Invoke-ApplySubtitles {
    param(
        [object]$Config,
        [string]$VideoPath,
        [string]$SubtitlePath,
        [string]$OutputPath,
        [ValidateSet("burn", "mux")]
        [string]$Mode = "burn"
    )

    $ffmpeg = $Config.ffmpeg.ffmpeg_exe
    if (-not $ffmpeg) { $ffmpeg = "ffmpeg" }

    if ($Mode -eq "burn") {
        # Burn-in subtitles (re-encode). Use ass filter when .ass is provided.
        $ext = [IO.Path]::GetExtension($SubtitlePath).ToLowerInvariant()
        $subEsc = Escape-FfmpegFilterPath -Path $SubtitlePath
        if ($ext -eq ".ass") {
            & $ffmpeg -y -i $VideoPath -vf "ass='$subEsc'" -c:a copy $OutputPath
        } else {
            & $ffmpeg -y -i $VideoPath -vf "subtitles='$subEsc'" -c:a copy $OutputPath
        }
        return
    }

    # Mux as soft subtitles (no re-encode). Best-effort defaults for mp4.
    & $ffmpeg -y -i $VideoPath -i $SubtitlePath -c copy -c:s mov_text $OutputPath
}

function Invoke-PythonTool {
    param(
        [string]$RepoRoot,
        [string]$ScriptRelPath,
        [string[]]$ArgsList
    )

    $venvPython = Join-Path $RepoRoot ".venv\\Scripts\\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "Missing venv. Run: .\\setup.ps1"
    }

    $scriptPath = Join-Path $RepoRoot $ScriptRelPath
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "Missing script: $scriptPath"
    }

    & $venvPython $scriptPath @ArgsList
}

function Get-AutoModelBySize {
    param(
        [object]$Config,
        [string]$MediaPath
    )

    $policy = $Config.transcription.model_policy
    if (-not $policy -or -not $policy.enabled) {
        if ($policy -and $policy.fallback_model) { return [string]$policy.fallback_model }
        return "turbo"
    }

    $fallback = "turbo"
    if ($policy.fallback_model) { $fallback = [string]$policy.fallback_model }

    try {
        $sizeBytes = (Get-Item -LiteralPath $MediaPath).Length
        $sizeMb = $sizeBytes / 1MB
    } catch {
        return $fallback
    }

    foreach ($rule in $policy.rules) {
        if (-not $rule -or -not $rule.model) { continue }
        if ($null -eq $rule.max_mb) { return [string]$rule.model }
        if ($sizeMb -le [double]$rule.max_mb) { return [string]$rule.model }
    }

    return $fallback
}

$repoRoot = Resolve-RepoRoot -ScriptDir $scriptDir
$config = Get-Agent1Config -RepoRoot $repoRoot
$outDir = Get-DefaultOutputDir -RepoRoot $repoRoot -Config $config -Override $OutputDir

switch ($Task) {
    "video.translate" {
        Assert-InputPath -Path $InputPath
        # Prefer faster-whisper-xxl.exe (if configured), fallback to turbo-transcribe.
        if ($config.transcription.faster_whisper_exe -and (Test-Path -LiteralPath $config.transcription.faster_whisper_exe)) {
            $m = Get-AutoModelBySize -Config $config -MediaPath $InputPath
            Write-Host "自動選模型: $m" -ForegroundColor Cyan
            Invoke-FasterWhisperExe -Config $config -MediaPath $InputPath -OutputDir $outDir -Model $m -Translate
        } else {
            Invoke-TurboTranscribe -Config $config -MediaPath $InputPath -OutputDir $outDir -Translate
        }
    }
    "video.subtitles.generate" {
        Assert-InputPath -Path $InputPath
        if ($config.transcription.faster_whisper_exe -and (Test-Path -LiteralPath $config.transcription.faster_whisper_exe)) {
            $m = Get-AutoModelBySize -Config $config -MediaPath $InputPath
            Write-Host "自動選模型: $m" -ForegroundColor Cyan
            Invoke-FasterWhisperExe -Config $config -MediaPath $InputPath -OutputDir $outDir -Model $m
        } else {
            Invoke-TurboTranscribe -Config $config -MediaPath $InputPath -OutputDir $outDir
        }
    }
    "video.subtitles.design" {
        Assert-InputPath -Path $InputPath
        $assOut = Join-Path $outDir (([IO.Path]::GetFileNameWithoutExtension($InputPath)) + ".ass")
        Invoke-PythonTool -RepoRoot $repoRoot -ScriptRelPath "agents\\agent1-video-subtitle\\tools\\srt_to_ass.py" -ArgsList @(
            "--input", $InputPath,
            "--output", $assOut
        )
    }
    "video.subtitles.preview" {
        Assert-InputPath -Path $InputPath
        Invoke-PythonTool -RepoRoot $repoRoot -ScriptRelPath "agents\\agent1-video-subtitle\\tools\\subtitle_preview.py" -ArgsList @(
            "--subtitles", $InputPath
        )
    }
    "video.ui" {
        $ui = Join-Path $repoRoot "agents\\agent1-video-subtitle\\ui\\subtitle_studio.py"
        if (-not (Test-Path -LiteralPath $ui)) {
            throw "Missing UI: $ui"
        }
        Invoke-PythonTool -RepoRoot $repoRoot -ScriptRelPath "agents\\agent1-video-subtitle\\ui\\subtitle_studio.py" -ArgsList @()
    }
    "video.realtime.ui" {
        Invoke-PythonTool -RepoRoot $repoRoot -ScriptRelPath "agents\\agent1-video-subtitle\\ui\\realtime_studio.py" -ArgsList @()
    }
    "subtitles.translate.pro" {
        Assert-InputPath -Path $InputPath
        $inPath = (Resolve-Path -LiteralPath $InputPath).Path
        if (-not ($inPath.ToLowerInvariant().EndsWith(".srt"))) {
            throw "subtitles.translate.pro 目前僅支援 .srt 輸入: $inPath"
        }
        $base = [IO.Path]::GetFileNameWithoutExtension($inPath)
        $outSrt = Join-Path $outDir ($base + ".zh-TW.srt")
        Invoke-PythonTool -RepoRoot $repoRoot -ScriptRelPath "agents\\agent1-video-subtitle\\tools\\copilot_translate_srt.py" -ArgsList @(
            "--input", $inPath,
            "--output", $outSrt
        )
        Write-Host "OK: $outSrt" -ForegroundColor Green
    }
    "video.apply" {
        Assert-InputPath -Path $InputPath
        throw "video.apply requires -InputPath as video path and a subtitle path; use Apply-Subtitles.ps1 for now."
    }
    "agent2.excel.summarize" {
        Assert-InputPath -Path $InputPath
        & (Join-Path $repoRoot "agents\\agent2-doc-excel\\Invoke-Agent2.ps1") -Task "excel.summarize" -InputPath $InputPath -OutputDir $outDir
    }
    "agent2.excel.automanage" {
        Assert-InputPath -Path $InputPath
        & (Join-Path $repoRoot "agents\\agent2-doc-excel\\Invoke-Agent2.ps1") -Task "excel.automanage" -InputPath $InputPath -OutputDir $outDir
    }
}
