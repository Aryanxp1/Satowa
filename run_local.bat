@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "ENVIRONMENT=development"
set "LOCAL_DEMO=true"

set "PYTHON_CMD="
if exist "%BACKEND_DIR%\venv\Scripts\python.exe" set "PYTHON_CMD=%BACKEND_DIR%\venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" set "PYTHON_CMD=%BACKEND_DIR%\.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%ROOT_DIR%venv\Scripts\python.exe" set "PYTHON_CMD=%ROOT_DIR%venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%ROOT_DIR%.venv\Scripts\python.exe" set "PYTHON_CMD=%ROOT_DIR%.venv\Scripts\python.exe"

if not defined PYTHON_CMD (
    echo [Setowa] Creating virtual environment at backend\venv...
    python -m venv "%BACKEND_DIR%\venv"
    if errorlevel 1 (
        echo Error: Python was not found in PATH.
        exit /b 1
    )
    set "PYTHON_CMD=%BACKEND_DIR%\venv\Scripts\python.exe"
    echo [Setowa] Installing requirements...
    "%PYTHON_CMD%" -m pip install -q -r "%BACKEND_DIR%\requirements.txt"
)

"%PYTHON_CMD%" "%BACKEND_DIR%\scripts\start_demo.py" %*
