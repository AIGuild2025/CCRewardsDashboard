# Windows equivalent of setup.sh

@echo off
echo ============================================================
echo   Credit Card Intelligence Platform - Setup
echo ============================================================
echo.

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
echo Virtual environment ready

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -q -r requirements.txt

REM Install Playwright browsers
echo Installing Playwright browsers...
playwright install chromium

REM Create environment file
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
    echo IMPORTANT: Edit .env with your configuration
)

REM Create cache directories
if not exist "cache\fingerprints" mkdir cache\fingerprints
if not exist "logs" mkdir logs
if not exist "screenshots" mkdir screenshots

REM Run tests
echo Running tests...
pytest tests/ -q

echo.
echo ============================================================
echo   Setup complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Edit .env with your configuration
echo   2. Run: python scheduler/run_pipeline.py --bank Chase
echo.
echo For more info, see README.md and GETTING_STARTED.md
