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

set /p USER_QUERY=請輸入文件問題：
if "%USER_QUERY%"=="" (
  echo 未輸入 query，取消執行。
  exit /b 1
)

python main.py --task rag --query "%USER_QUERY%"
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% neq 0 (
  echo 執行失敗，錯誤碼：%EXIT_CODE%
) else (
  echo 執行完成。
)

exit /b %EXIT_CODE%
