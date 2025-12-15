@echo off
REM RAG Chatbot Server Launcher
REM Quick start script untuk Windows

echo ========================================
echo RAG Chatbot Server Launcher
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python first.
    pause
    exit /b 1
)

REM Check if venv is activated
if "%VIRTUAL_ENV%"=="" (
    echo [WARNING] Virtual environment not activated
    echo Activating venv...
    call venv\Scripts\activate.bat
)

REM Check dependencies
echo [*] Checking dependencies...
python -c "import fastapi; import uvicorn" 2>nul
if errorlevel 1 (
    echo [*] Installing server dependencies...
    pip install -q fastapi uvicorn python-multipart
)

echo [*] Checking RAG dependencies...
python -c "import lightrag; import easyocr" 2>nul
if errorlevel 1 (
    echo [*] Installing RAG dependencies...
    pip install -q -r requirements.txt
)

echo.
echo [✓] All dependencies ready
echo [*] Starting server...
echo.

REM Start server with reload enabled for development
python -m uvicorn main_server:app --reload --host 0.0.0.0 --port 8000

REM If server exits
echo.
echo [!] Server stopped
pause
