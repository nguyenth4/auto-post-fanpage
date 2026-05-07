@echo off
title Khoi chay Dashboard Auto Post Fanpage
echo Dang khoi chay chuong trinh, vui long cho trong giay lat...
echo.
echo ======================================================
echo    LUNG LINH DECOR - AUTOMATION TOOLS
echo ======================================================
echo.

REM Chay Flask app bang moi truong ao
start http://127.0.0.1:5000
.\.venv\Scripts\python app.py

pause
