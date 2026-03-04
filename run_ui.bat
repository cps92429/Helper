@echo off
setlocal

if not exist .venv\Scripts\activate.bat (
  echo 找不到 .venv，請先執行 bootstrap.bat
  exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo 啟用虛擬環境失敗。
  exit /b 1
)

python -c "import streamlit" >nul 2>nul
if errorlevel 1 (
  echo 尚未安裝 streamlit，正在安裝...
  pip install streamlit
  if errorlevel 1 (
    echo 安裝 streamlit 失敗。
    exit /b 1
  )
)

echo 啟動 UI 面板中...
streamlit run ui_panel.py
exit /b %errorlevel%
