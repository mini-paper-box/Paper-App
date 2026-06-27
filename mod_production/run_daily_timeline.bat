
@echo off
:: Force the script to change its current working directory to where this file lives
REM cd /d "%~dp0"
call C:\Users\sang.n\AppData\Local\anaconda3\Scripts\activate.bat
call conda activate python_base

cd /d "C:\Users\sang.n\OneDrive - whitebird.ca\Paper App"

python -m mod_production.predict_daily_leadtime

pause