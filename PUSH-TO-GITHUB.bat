@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Push VideoRemixer len GitHub
echo.
set /p GH_USER="GitHub username cua ban: "
if "%GH_USER%"=="" (echo Can nhap username! & pause & exit /b 1)

set REPO_NAME=VideoRemixer
set REPO_URL=https://github.com/%GH_USER%/%REPO_NAME%.git

where gh >nul 2>&1
if %errorlevel%==0 (
    echo Phat hien GitHub CLI, tao repo tu dong...
    gh repo create %REPO_NAME% --public --description "Tao hang tram bien the video quang cao" 2>nul
) else (
    echo Tao repo tay:
    echo   1. Mo https://github.com/new
    echo   2. Ten: %REPO_NAME% - Public - KHONG tick README
    echo   3. Bam Create repository
    echo.
    pause
)

git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main
echo.
echo Dang push...
git push -u origin main

echo.
echo Done! Repo tai: https://github.com/%GH_USER%/%REPO_NAME%
pause
