@echo off
chcp 65001 >nul

set "CUR_DIR=%~dp0"
for %%I in ("%CUR_DIR%..") do set "PARENT_DIR=%%~fI"

if not exist "%PARENT_DIR%\MaiCoreStart-V4.0.0.3-beta.exe" (
    echo Error: Cannot find MaiCoreStart-V4.0.0.3-beta.exe
    echo Expected path: %PARENT_DIR%\MaiCoreStart-V4.0.0.3-beta.exe
    pause
    exit /b 1
)

cd /d "%PARENT_DIR%"
echo Starting MaiCoreStart-V4.0.0.3-beta.exe...
start "" "%PARENT_DIR%\MaiCoreStart-V4.0.0.3-beta.exe"

if %errorlevel% equ 0 (
    echo Started successfully!
) else (
    echo Failed to start, error code: %errorlevel%
    pause
)