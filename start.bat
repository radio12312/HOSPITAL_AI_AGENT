@echo off
rem One-command start (Windows): checks Docker, asks for the NVIDIA key once, starts the stack.
setlocal
cd /d "%~dp0"
title Hospital Workflow Agent
echo.
echo  Hospital Workflow Agent
echo  -----------------------

docker info >nul 2>&1
if errorlevel 1 (
    echo  Docker is not running. Install Docker Desktop from https://www.docker.com/products/docker-desktop/
    echo  start it, wait until it says "Engine running", then run start.bat again.
    pause
    exit /b 1
)

if not exist ".env" copy /y ".env.example" ".env" >nul

findstr /r /c:"^NVIDIA_API_KEY=nvapi-your-key-here" /c:"^NVIDIA_API_KEY=$" ".env" >nul
if not errorlevel 1 (
    echo.
    echo  An NVIDIA API key is needed ^(free^): https://build.nvidia.com
    echo  Open any model, click "Get API Key", then paste it below. It is saved only to .env.
    powershell -NoProfile -Command ^
      "$k = Read-Host '  NVIDIA API key (input hidden)' -AsSecureString;" ^
      "$p = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($k));" ^
      "if (-not $p) { exit 1 };" ^
      "(Get-Content .env) -replace '^NVIDIA_API_KEY=.*', ('NVIDIA_API_KEY=' + $p.Trim()) | Set-Content -Encoding ascii .env"
    if errorlevel 1 (
        echo  No key entered.
        pause
        exit /b 1
    )
    echo   ^> API key saved to .env
)

echo   ^> Building and starting containers (first run: 3-5 minutes, includes data generation and model training)...
docker compose up --build -d
if errorlevel 1 (
    echo  docker compose failed - see the messages above.
    pause
    exit /b 1
)

echo   ^> Waiting for the app to become ready...
for /l %%i in (1,1,120) do (
    curl -s -o nul -f http://localhost:8080/api/health && goto ready
    timeout /t 3 /nobreak >nul
)
echo  The app did not become ready in time. Check logs with: docker compose logs backend
pause
exit /b 1

:ready
echo   ^> Ready: http://localhost:8080   (demo login: admin / admin123)
echo     Stop with: docker compose down
start "" http://localhost:8080
