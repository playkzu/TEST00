@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Flask Hello World 網站伺服器
echo ==============================================
echo   正在啟動 Flask Hello World 一頁式網站...
echo ==============================================
echo.

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" app.py
) else if exist "C:\SoftWare\Anaconda\python.exe" (
    "C:\SoftWare\Anaconda\python.exe" app.py
) else (
    python app.py
)

if errorlevel 1 (
    echo.
    echo 執行發生錯誤，請確認 Python 及 Flask 套件是否正確安裝。
    pause
)
