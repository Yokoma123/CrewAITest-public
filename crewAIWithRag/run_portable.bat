@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "STUDENT_INFO_DATA_DIR=%~dp0data"
set "STUDENT_DB_PATH=%STUDENT_INFO_DATA_DIR%\students.db"
set "STUDENT_INFO_PORT=8013"

if exist "%~dp0StudentInfoSystem.exe" (
  start "" "%~dp0StudentInfoSystem.exe"
  exit /b 0
)

if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0portable_launcher.py"
  exit /b %errorlevel%
)

python "%~dp0portable_launcher.py"
