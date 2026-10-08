@echo off
cd /d "%~dp0"
chcp 65001 >nul
title 訂單管理系統 (Flask + SQLite + Bootstrap 5)
echo ==============================================================
echo   正在啟動 訂單管理系統 (Flask + SQLite + Bootstrap 5)...
echo   預設管理員帳號: admin
echo   預設管理員密碼: admin123
echo   系統首頁網址:   http://127.0.0.1:5000
echo ==============================================================
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
    echo 執行發生錯誤，請確認 Python 及相關套件是否已安裝。
    pause
)
