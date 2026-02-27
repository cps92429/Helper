@echo off
setlocal

if "%~1"=="" (
  echo Drag a video file onto this .bat
  exit /b 1
)

set REPO=%~dp0..\..
pushd "%REPO%" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$repo=(Get-Location).Path; $py=Join-Path $repo '.venv\\Scripts\\python.exe'; if (!(Test-Path $py)) { throw 'Missing venv. Run .\\setup.ps1 -Target Agent1' }; " ^
  "& $py '.\\agents\\agent1-video-subtitle\\tools\\studio_cli.py' --input '%~1' --transcribe --smart-segment --pro-translate --bilingual-ass --burn-in"

popd >nul
endlocal

