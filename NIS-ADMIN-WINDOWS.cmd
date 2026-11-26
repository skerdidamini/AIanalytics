@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 start-local.py --demo --admin %*
goto finished
:use_python
where python >nul 2>nul
if errorlevel 1 goto missing
python start-local.py --demo --admin %*
goto finished
:missing
echo Install Python 3.12 from python.org, then run this file again.
echo During installation select Add python.exe to PATH.
pause
exit /b 1
:finished
set "startup_result=%errorlevel%"
if not "%startup_result%"=="0" echo Startup failed. Read the messages above or see FILLIMI-WINDOWS.md.
pause
exit /b %startup_result%
