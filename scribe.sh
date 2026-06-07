#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# SCRIBE - YouTube Audio Downloader & Transcriber (Linux/macOS/WSL)
# Shell port of scribe.bat
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ==== CONFIGURATION (override via args or environment) ====
#   URL:       1st arg  or $YOUTUBE_URL
#   Filename:  2nd arg  or $EXPORT_FILENAME (defaults to a timestamp)
#   Dir:       $TRANSCRIPT_DIR (defaults to ./transcripts next to this script)
TRANSCRIPT_DIR="${TRANSCRIPT_DIR:-$SCRIPT_DIR/transcripts}"
YOUTUBE_URL="${1:-${YOUTUBE_URL:-}}"
EXPORT_FILENAME="${2:-${EXPORT_FILENAME:-}}"
# ============================================================

if [[ -z "$YOUTUBE_URL" ]]; then
    echo "[!] ERROR: No YouTube URL provided."
    echo "Usage: ./scribe.sh \"https://youtube.com/watch?v=...\" [\"Export Filename\"]"
    echo "   or: YOUTUBE_URL=... EXPORT_FILENAME=... ./scribe.sh"
    exit 1
fi

if [[ -z "$EXPORT_FILENAME" ]]; then
    EXPORT_FILENAME="transcript_$(date +%Y%m%d_%H%M%S)"
    echo "[*] No export filename given; using: $EXPORT_FILENAME"
fi

# ==== Dependency checks ====
for cmd in yt-dlp ffmpeg python3; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[!] ERROR: required command '$cmd' not found in PATH."
        echo "    Install it, e.g.:  sudo apt install ffmpeg  &&  pip install yt-dlp faster-whisper"
        exit 1
    fi
done

mkdir -p "$TRANSCRIPT_DIR"

# Temp dir for audio, auto-cleaned on exit (success, error, or Ctrl+C)
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/scribe_audio.XXXXXX")"
trap 'rm -rf "$TEMP_DIR"' EXIT

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
AUDIO_FILE="$TEMP_DIR/$TIMESTAMP.mp3"

echo "============================================================"
echo "  SCRIBE - Downloading and Transcribing"
echo "============================================================"
echo "[*] Download URL:   $YOUTUBE_URL"
echo "[*] Export file:    $EXPORT_FILENAME.txt"
echo "[*] Transcript dir: $TRANSCRIPT_DIR"
echo ""
echo "[*] Downloading audio (temporary)..."

# -o uses %(ext)s so yt-dlp's post-extraction mp3 lands at the expected path
yt-dlp -x --audio-format mp3 \
    --user-agent "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
    --referer "https://www.google.com/" \
    -o "$TEMP_DIR/$TIMESTAMP.%(ext)s" \
    "$YOUTUBE_URL"

if [[ ! -f "$AUDIO_FILE" ]]; then
    echo "[!] Could not find downloaded audio file ($AUDIO_FILE)"
    exit 1
fi

echo "[*] Audio saved to: $AUDIO_FILE"
echo ""
echo "[*] Starting transcription..."
echo "[*] Output is written to $EXPORT_FILENAME.txt as it's generated (Ctrl+C to stop)"
echo "============================================================"
echo ""

python3 "$SCRIPT_DIR/transcribe_stream.py" "$AUDIO_FILE" "$TRANSCRIPT_DIR/$EXPORT_FILENAME"

echo ""
echo "============================================================"
echo "[+] Transcription complete!"
echo "[*] Final file: $TRANSCRIPT_DIR/$EXPORT_FILENAME.txt"
echo "============================================================"
