@echo off
setlocal

set "PACKAGE_DIR=%~dp0"
for %%I in ("%PACKAGE_DIR%.") do set "PACKAGE_DIR=%%~fI"

set "INSTALLER=%PACKAGE_DIR%\scripts\install-test-package.ps1"
if not exist "%INSTALLER%" (
    set "INSTALLER=%PACKAGE_DIR%\backend\theseus-core-server\scripts\install-test-package.ps1"
)

if not exist "%INSTALLER%" (
    echo Theseus test package installer was not found.
    echo.
    echo Expected one of:
    echo   %PACKAGE_DIR%\scripts\install-test-package.ps1
    echo   %PACKAGE_DIR%\backend\theseus-core-server\scripts\install-test-package.ps1
    echo.
    echo Put this file next to the package scripts folder, or run it from the repository root.
    pause
    exit /b 1
)

echo Theseus test package setup
echo Package : %PACKAGE_DIR%
echo Installer: %INSTALLER%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%INSTALLER%" -PackagePath "%PACKAGE_DIR%" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Theseus test package setup failed with exit code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

echo Theseus test package setup complete.
pause
exit /b 0
