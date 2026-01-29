@echo off
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Open the default browser
start http://127.0.0.1:6680

REM Start the application
python main.py

pause
