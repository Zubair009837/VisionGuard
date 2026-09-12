@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo VisionGuard AI - Frontend Dependency Setup
echo ============================================
echo.
echo Removing any old npm install that may contain
echo a platform-specific Rolldown native binding...
if exist node_modules rmdir /s /q node_modules
if exist package-lock.json del /f /q package-lock.json

echo.
echo Installing fresh frontend dependencies...
npm install
if errorlevel 1 (
    echo.
    echo [ERROR] npm install failed.
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully.
echo You can now run: npm run dev
pause
