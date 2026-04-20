@echo off
REM Pull latest production backup to local machine
REM Run this weekly for off-server backup protection

SET REMOTE=root@204.168.146.253
SET KEY=c:\development\btc-bot\btc-bot-deploy-v2
SET LOCAL_DIR=c:\development\btc-bot\backups
SET TIMESTAMP=%date:~-4%%date:~3,2%%date:~0,2%

echo ================================================
echo   Production Backup Pull
echo ================================================
echo.
echo Remote: %REMOTE%
echo Local:  %LOCAL_DIR%
echo.

REM Create backup directory if doesn't exist
if not exist "%LOCAL_DIR%" mkdir "%LOCAL_DIR%"

echo Pulling latest backup from production server...
echo.

scp -i "%KEY%" %REMOTE%:/home/btc-bot/backups/database/btc_bot_latest.db.gz "%LOCAL_DIR%\btc_bot_%TIMESTAMP%.db.gz"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Backup pulled successfully!
    echo.
    echo Location: %LOCAL_DIR%\btc_bot_%TIMESTAMP%.db.gz
    echo.

    REM Show file size
    dir "%LOCAL_DIR%\btc_bot_%TIMESTAMP%.db.gz" | findstr "btc_bot"

    echo.
    echo To extract:
    echo   gunzip "%LOCAL_DIR%\btc_bot_%TIMESTAMP%.db.gz"
    echo.
    echo To verify:
    echo   sqlite3 "%LOCAL_DIR%\btc_bot_%TIMESTAMP%.db" "PRAGMA integrity_check;"
    echo.
) else (
    echo.
    echo [ERROR] Backup pull failed!
    echo Check SSH connection and key path.
    exit /b 1
)

REM List all local backups
echo.
echo Local backups:
dir /B "%LOCAL_DIR%\btc_bot_*.db.gz" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   (no backups found)
)

echo.
pause