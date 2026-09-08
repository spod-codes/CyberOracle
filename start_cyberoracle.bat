@echo off
echo ========================================================
echo     CYBERORACLE - SIH 2026 PRESENTATION BOOTSTRAPPER
echo ========================================================

echo [1/3] Starting MongoDB database in the background...
start /b "" "C:\Users\spodc\mongodb\mongodb-win32-x86_64-windows-8.0.4\bin\mongod.exe" --dbpath "c:\Users\spodc\mongodb\data\db"

echo [2/3] Starting FastAPI Backend Engine...
cd backend
start /b "" python -m uvicorn server:app --port 8001
cd ..

echo [3/3] Starting React Frontend...
cd frontend
start /b "" npm run dev
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
