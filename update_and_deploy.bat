@echo off
REM Daily update workflow — run this after Garmin scrape
cd /d "%~dp0"

echo.
echo ==========================================
echo  Korat 21 Dashboard - Update and Deploy
echo ==========================================
echo.

echo [1/3] Building dashboard...
python build_dashboard.py
if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo [2/3] Committing changes...
git add .
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "update %date% %time:~0,5%"
) else (
    echo No changes to commit.
    pause
    exit /b 0
)

echo.
echo [3/3] Pushing to GitHub...
git push
if errorlevel 1 (
    echo ERROR: Push failed - check internet/auth
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Done! Refresh dashboard on phone in 1 min
echo  https://pattanan-th.github.io/running-dashboard/dashboard.html
echo ==========================================
pause
