@echo off
REM ----------------------------------------
REM 1. Activate your virtual environment (if using Anaconda or venv)
REM Update the path below to your Python environment
REM ----------------------------------------
call "C:\Users\sang.n\AppData\Local\anaconda3\Scripts\activate.bat"

REM ----------------------------------------
REM 2. Define paths
REM ----------------------------------------
set SCRIPT_PATH="C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\auto scheduler\order_mailer.py"
set LOG_PATH="C:\Users\sang.n\OneDrive - whitebird.ca\Paper App\auto scheduler\order_mailer.log"

REM ----------------------------------------
REM 3. Run the Python script and log output
REM ----------------------------------------
echo Running Order Mailer...
python %SCRIPT_PATH% >> %LOG_PATH% 2>&1

REM ----------------------------------------
REM 4. Print completion message
REM ----------------------------------------
echo Script finished. Check log at %LOG_PATH%
pause
