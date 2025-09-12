@echo off
echo LabJack Bridge Quick Installer
echo ===============================

REM Create directories
mkdir C:\LabJackBridge
mkdir C:\LabJackBridge\src
mkdir C:\LabJackBridge\config
mkdir C:\LabJackBridge\logs

REM Create Python virtual environment
echo Creating virtual environment...
C:\Users\Brigade\AppData\Local\Microsoft\WindowsApps\python.exe -m venv C:\LabJackBridge\venv

REM Install packages
echo Installing packages...
C:\LabJackBridge\venv\Scripts\pip.exe install --upgrade pip
C:\LabJackBridge\venv\Scripts\pip.exe install fastapi uvicorn websockets aiofiles requests

REM Create start script
echo @echo off > C:\LabJackBridge\start.bat
echo cd /d C:\LabJackBridge >> C:\LabJackBridge\start.bat
echo echo Starting LabJack Bridge... >> C:\LabJackBridge\start.bat
echo C:\LabJackBridge\venv\Scripts\python.exe src\labjack_bridge_service.py >> C:\LabJackBridge\start.bat
echo pause >> C:\LabJackBridge\start.bat

echo ===============================
echo Installation Complete!
echo To start: C:\LabJackBridge\start.bat
echo ===============================
pause