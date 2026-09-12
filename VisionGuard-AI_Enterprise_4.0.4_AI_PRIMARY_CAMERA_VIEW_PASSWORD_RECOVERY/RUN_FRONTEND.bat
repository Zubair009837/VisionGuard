@echo off
setlocal
cd /d "%~dp0frontend"
echo ================================================
echo VisionGuard AI - Frontend V4
echo Folder: %CD%
echo ================================================
where node >nul 2>nul
if errorlevel 1 (echo Node.js is not installed/on PATH. & pause & exit /b 1)

echo.
echo Checking frontend dependencies...
npm install
if errorlevel 1 (
    echo.
    echo First npm install failed. Cleaning node_modules and package-lock.json...
    if exist node_modules rmdir /s /q node_modules
    if exist package-lock.json del /f /q package-lock.json
    echo Retrying with a clean dependency installation...
    npm install
    if errorlevel 1 (echo npm install failed after clean retry. & pause & exit /b 1)
)

echo.
echo Starting frontend...
echo Keep this window OPEN.
echo.
npm run dev -- --host 0.0.0.0
pause
