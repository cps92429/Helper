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

echo 請輸入要分析的程式碼（單行）；若含空白請直接貼上：
set /p USER_CODE=Code> 
if "%USER_CODE%"=="" (
  echo 未輸入程式碼，取消執行。
  exit /b 1
)

python main.py --task code --code "%USER_CODE%"
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% neq 0 (
  echo 執行失敗，錯誤碼：%EXIT_CODE%
) else (
  echo 執行完成。
)

exit /b %EXIT_CODE%
