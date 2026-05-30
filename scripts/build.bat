@echo off
REM MouseShare PyInstaller Build Script
REM Run on Windows with Python 3.11+ installed

echo ========================================
echo   MouseShare - Build Script
echo ========================================

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Please install Python 3.11+
    exit /b 1
)

REM Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies
    exit /b 1
)

REM Run unit tests
echo [2/3] Running unit tests...
python -m pytest tests/ -v --tb=short 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Tests failed — continuing with build anyway
)

REM Build with PyInstaller
echo [3/3] Building executable...
python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name MouseShare ^
    --add-data "assets;assets" ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import PySide6.QtGui ^
    --hidden-import pynput.mouse ^
    --hidden-import pynput._util ^
    --hidden-import src.shared.protocol ^
    --hidden-import src.shared.transport ^
    --hidden-import src.shared.config ^
    --hidden-import src.shared.state_machine ^
    --hidden-import src.host.input_capture ^
    --hidden-import src.host.boundary_engine ^
    --hidden-import src.host.cursor_controller ^
    --hidden-import src.host.state_machine ^
    --hidden-import src.target.rfcomm_server ^
    --hidden-import src.target.input_injector ^
    --hidden-import src.target.state_machine ^
    --hidden-import src.ui.main_window ^
    --hidden-import src.ui.device_list ^
    --hidden-import src.ui.layout_config ^
    --hidden-import src.ui.status_page ^
    --hidden-import src.ui.tray ^
    --clean ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller build failed
    exit /b 1
)

echo ========================================
echo   Build complete!
echo   Output: dist\MouseShare.exe
echo ========================================
dir dist\MouseShare.exe
