@echo off
chcp 65001 >nul
title Video Bulk Remixer
echo.
echo  ╔══════════════════════════════════════╗
echo  ║     Video Bulk Remixer               ║
echo  ║     Dang khoi dong...                ║
echo  ╚══════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Chua cai Python. Tai tai: https://www.python.org/downloads/
    echo Chon "Add Python to PATH" khi cai dat.
    pause
    exit /b 1
)

:: Setup venv if needed
if not exist ".venv" (
    echo [1/3] Tao moi truong ao...
    python -m venv .venv
    echo [2/3] Cai thu vien...
    .venv\Scripts\pip install -e ".[dev]" --quiet
    echo [3/3] Xong!
) else (
    echo Moi truong da san sang.
)

echo.
echo Dang mo giao dien...
echo Dong cua so nay hoac bam Ctrl+C de thoat.
echo.
.venv\Scripts\python -m web.server
