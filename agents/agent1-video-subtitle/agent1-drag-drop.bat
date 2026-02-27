@echo off
setlocal

if "%~1"=="" (
  echo Drag a media file onto this .bat
  exit /b 1
)

set REPO=%~dp0..\..
pushd "%REPO%" >nul

powershell -NoProfile -ExecutionPolicy Bypass -File ".\agents\agent1-video-subtitle\OneClick.ps1" "%~1"

popd >nul
endlocal
