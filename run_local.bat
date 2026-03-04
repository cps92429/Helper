@echo off
setlocal EnableDelayedExpansion

if not exist .venv\Scripts\activate.bat (
  echo 找不到 .venv，請先執行 bootstrap.bat
  exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo 啟用虛擬環境失敗。
  exit /b 1
)

set /p USER_PROMPT=請輸入 prompt：
if "%USER_PROMPT%"=="" (
  echo 未輸入 prompt，取消執行。
  exit /b 1
)

python local_ai.py --prompt "%USER_PROMPT%"
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% neq 0 (
  echo 執行失敗，錯誤碼：%EXIT_CODE%
) else (
  echo 執行完成。
)

exit /b %EXIT_CODE%
