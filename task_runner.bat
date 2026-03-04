@echo off
setlocal

REM 自動化排程入口：將所有參數原樣轉給 main.py
if "%~1"=="" (
  echo 用法：task_runner.bat --task rag --query "請總結 docs 重點"
  echo 用法：task_runner.bat --task code --code "try: pass\nexcept Exception: pass"
  echo 用法：task_runner.bat --task local --prompt "請幫我生成 Python 函式"
  exit /b 1
)

python main.py %*
exit /b %errorlevel%
