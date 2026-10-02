@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
py -m gpslab.gui
if errorlevel 1 (
  echo.
  echo GPS-GUI exited with an error.
  echo If dependencies are missing, run:
  echo   py -m pip install -e .
  echo.
  pause
)
endlocal
