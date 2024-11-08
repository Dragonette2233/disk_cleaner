@echo off
:: Проверка прав администратора
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Запуск с правами администратора...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Активация виртуального окружения и запуск Python-скрипта
call .env\Scripts\activate
python main.py
pause