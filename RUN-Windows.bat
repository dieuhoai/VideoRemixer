@echo off
chcp 65001 >nul
title Video Bulk Remixer
cd /d "%~dp0"
echo.
echo  ======================================
echo       Video Bulk Remixer
echo       Dang khoi dong...
echo  ======================================
echo.

:: Tim Python 3.10 tro len
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [LOI] Chua co Python 3.10 tro len. Tai tai https://www.python.org/downloads/
    echo Chon "Add Python to PATH" khi cai dat.
    pause
    exit /b 1
)

set "CHECK=import fastapi, uvicorn, numpy, cv2, PIL"

if not exist ".venv\Scripts\python.exe" goto install
.venv\Scripts\python.exe -c "%CHECK%" >nul 2>&1
if errorlevel 1 goto install
echo Moi truong da san sang.
goto run

:install
echo [1/3] Tao moi truong ao...
if exist ".venv" rmdir /s /q ".venv"
%PY% -m venv .venv
if errorlevel 1 goto fail_venv
echo [2/3] Cai thu vien (co the mat vai phut)...
.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
.venv\Scripts\python.exe -m pip install .
if errorlevel 1 goto fail_install
.venv\Scripts\python.exe -c "%CHECK%" >nul 2>&1
if errorlevel 1 goto fail_install
echo [3/3] Xong!
echo.

:run
echo Dang mo giao dien...
echo Dong cua so nay hoac bam Ctrl+C de thoat.
echo.
.venv\Scripts\python.exe -m web.server
pause
exit /b 0

:fail_venv
echo [LOI] Khong tao duoc moi truong ao.
pause
exit /b 1

:fail_install
echo [LOI] Cai thu vien that bai. Chup lai cac dong loi phia tren va gui cho nguoi ho tro.
if exist ".venv" rmdir /s /q ".venv"
pause
exit /b 1
