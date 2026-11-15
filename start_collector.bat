@echo off
cd /d "%~dp0"
py app.py
if errorlevel 1 (
  echo.
  echo Prestige Price Collector could not start.
  echo Install Python 3.10+, install Tesseract OCR, then run:
  echo py -m pip install -r requirements.txt
)
pause
