@echo off
REM Windows Build Script for Apple Music Play History Converter

echo Building Apple Music Play History Converter for Windows...

REM Get script directory and project root
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

cd /d "%PROJECT_ROOT%"
echo Project root: %PROJECT_ROOT%

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Clean previous builds
echo Cleaning previous builds...
if exist "build_artifacts\build" rmdir /s /q "build_artifacts\build"
if exist "build_artifacts\dist" rmdir /s /q "build_artifacts\dist"
if exist "build_artifacts\*.zip" del /q "build_artifacts\*.zip"

REM Build the application
echo Building application...
cd build_artifacts
pyinstaller --clean --noconfirm build_windows.spec

REM Verify the build (onedir structure)
if exist "dist\Apple Music History Converter\Apple Music History Converter.exe" (
    echo Windows build successful!
    echo Executable location: %PROJECT_ROOT%\build_artifacts\dist\Apple Music History Converter\Apple Music History Converter.exe
    
    REM Get file size
    for %%A in ("dist\Apple Music History Converter\Apple Music History Converter.exe") do echo Executable size: %%~zA bytes
    
    REM Create zip package (entire directory)
    echo Creating distribution package...
    powershell -command "Compress-Archive -Path 'dist\Apple Music History Converter' -DestinationPath 'Apple_Music_History_Converter_Windows.zip'"
    
    echo Distribution package: %PROJECT_ROOT%\build_artifacts\Apple_Music_History_Converter_Windows.zip
) else (
    echo Build failed - Executable not found
    exit /b 1
)

echo Windows build complete!
pause
