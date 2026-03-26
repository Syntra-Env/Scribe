@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================
:: SCRIBE - YouTube Audio Downloader & Transcriber
:: ============================================================

:: ==== CONFIGURATION ====
set "TRANSCRIPT_DIR=C:\Syntra\Scribe\transcripts"
set "EXPORT_FILENAME=YT213 Why Supplications Not Accepted Answer from Quran"
:: ============================================================

set "YOUTUBE_URL=https://www.youtube.com/live/QolAmtu6aAs?si=zbZeK95DD_mhinhS"

:: ==== DOWNLOAD & TRANSCRIBE ====
echo ============================================================
echo  SCRIBE - Downloading and Transcribing
echo ============================================================
echo.

if "%EXPORT_FILENAME%"=="" (
    echo [!] ERROR: Please set EXPORT_FILENAME in this batch file
    pause
    exit /b 1
)

:: Check if URL was provided as argument
if not "%~1"=="" set "YOUTUBE_URL=%~1"

if "%YOUTUBE_URL%"=="https://www.youtube.com/watch?v=EXAMPLE" (
    echo [!] ERROR: Please set YOUTUBE_URL or pass URL as argument
    echo Usage: scribe.bat "https://youtube.com/watch?v=..."
    pause
    exit /b 1
)

:: Create transcripts directory if needed
if not exist "%TRANSCRIPT_DIR%" mkdir "%TRANSCRIPT_DIR%"

:: Set up temp directory for audio
set "TEMP_DIR=%TEMP%\scribe_audio"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

for /f %%a in ('powershell -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TIMESTAMP=%%a"
set "AUDIO_FILE=%TEMP_DIR%\%TIMESTAMP%.mp3"

echo [*] Download URL: %YOUTUBE_URL%
echo [*] Export file: %EXPORT_FILENAME%.txt
echo [*] Transcript dir: %TRANSCRIPT_DIR%
echo.
echo [*] Downloading audio (temporary)...
yt-dlp -x --audio-format mp3 --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" --referer "https://www.google.com/" -o "%AUDIO_FILE%.%%(ext)s" "%YOUTUBE_URL%"

if errorlevel 1 (
    echo [!] Download failed!
    rmdir "%TEMP_DIR%" 2>nul
    pause
    exit /b 1
)

:: Find the downloaded file
for %%F in ("%AUDIO_FILE%") do set "AUDIO_PATH=%%~fF"
if not exist "%AUDIO_PATH:.mp3=.mp3%" (
    for %%F in ("%TEMP_DIR%\%TIMESTAMP%.*") do set "AUDIO_PATH=%%~fF"
)

if not exist "%AUDIO_PATH%" (
    echo [!] Could not find downloaded audio file
    rmdir "%TEMP_DIR%" 2>nul
    pause
    exit /b 1
)

echo [*] Audio saved to: %AUDIO_PATH%
echo.
echo [*] Starting transcription...
echo [*] Output will be appended to %EXPORT_FILENAME%.txt as it's generated
echo [*] You can open and edit the file while transcription runs
echo [*] Press Ctrl+C to stop
echo.
echo ============================================================
echo.

python "%~dp0transcribe_stream.py" "%AUDIO_PATH%" "%TRANSCRIPT_DIR%\%EXPORT_FILENAME%"

:: Clean up temp audio file
del "%AUDIO_PATH%" 2>nul
for %%F in ("%AUDIO_PATH%.*") do del "%%~fF" 2>nul

echo.
echo ============================================================
echo [+] Transcription complete!
echo [*] Final file: %TRANSCRIPT_DIR%\%EXPORT_FILENAME%.txt
echo ============================================================
pause
