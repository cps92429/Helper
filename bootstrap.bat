@echo off
setlocal

echo [1/4] 建立 Python 虛擬環境 .venv ...
python -m venv .venv
if errorlevel 1 (
  echo 建立虛擬環境失敗，請確認 Python 已安裝並在 PATH 中。
  exit /b 1
)

echo [2/4] 啟用虛擬環境 ...
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo 啟用虛擬環境失敗。
  exit /b 1
)

echo [3/4] 升級 pip ...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo pip 升級失敗。
  exit /b 1
)

echo [4/4] 安裝 requirements.txt ...
pip install -r requirements.txt
if errorlevel 1 (
  echo 套件安裝失敗。
  exit /b 1
)

echo.
echo 初始化完成！你可以執行：
echo   task_runner.bat --task local --prompt "Write a hello-world function in Python"
exit /b 0
