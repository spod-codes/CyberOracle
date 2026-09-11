@echo off
echo ========================================================
echo     CYBERORACLE - LOCAL BOOTSTRAPPER
echo ========================================================

echo [1/2] Starting FastAPI Backend Engine...
cd backend
start "CyberOracle Backend" python -m uvicorn server:app --port 8000
cd ..

echo [2/2] Starting React Frontend...
cd frontend
start "CyberOracle Frontend" npm run dev
cd ..

echo.
echo Servers are booting up! 
echo Waiting 5 seconds before opening the browser...
timeout /t 5 /nobreak > nul

start http://localhost:3000

echo.
echo ========================================================
echo   CYBERORACLE IS LIVE. CLOSE THIS WINDOW TO SHUT DOWN.
echo ========================================================
pause
