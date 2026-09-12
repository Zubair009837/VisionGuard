@echo off
setlocal
cd /d "%~dp0backend"
echo ================================================
echo VisionGuard AI - Backend V5 Stable
echo Folder: %CD%
echo ================================================
where python >nul 2>nul
if errorlevel 1 (echo Python is not installed/on PATH. & pause & exit /b 1)
python -m pip install -r requirements.txt
if errorlevel 1 (echo Failed to install Python packages. & pause & exit /b 1)
echo.
echo Starting FastAPI backend on http://127.0.0.1:8010
echo Port 8000 is reserved for another local service.
echo Keep this window OPEN.
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
pause
