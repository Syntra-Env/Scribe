
import os
import json
import shutil
import tempfile
import subprocess
import re
from faster_whisper import WhisperModel
from flask import Flask, request, jsonify, Response, stream_with_context
from datetime import datetime

app = Flask(__name__)

# Standard Kalima directory for transcripts
SAVE_DIR = r"C:\Codex\Kalima\data\transcripts"

os.makedirs(SAVE_DIR, exist_ok=True)

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Load faster-whisper large-v3 with int8 quantization for CPU
print("[*] Loading faster-whisper large-v3 (int8, CPU)...")
model = WhisperModel("large-v3", device="cpu", compute_type="int8")
print("[*] Model loaded.")

def save_to_disk(text):
    """Utility to save transcript text to the standard data directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"voice_memo_{timestamp}.txt"
    filepath = os.path.join(SAVE_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filepath

@app.route('/transcribe', methods=['POST', 'OPTIONS'])
def transcribe():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    audio_file = request.files['file']

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        print(f"[*] Transcribing audio: {tmp_path}")
        segments, _ = model.transcribe(
            tmp_path, task="transcribe", language="en",
            beam_size=1, vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

        save_to_disk(text)
        print(f"[*] Automatically saved transcript to {SAVE_DIR}")

        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.route('/transcribe-youtube', methods=['POST', 'OPTIONS'])
def transcribe_youtube():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    data = request.json
    if not data or 'url' not in data:
        return jsonify({"error": "No URL provided"}), 400

    url = data['url'].strip()

    def sse(event, data):
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    def generate():
        tmp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(tmp_dir, "audio.%(ext)s")
        try:
            # --- Phase 1: Download ---
            yield sse("progress", {"phase": "download", "message": "Downloading audio..."})

            proc = subprocess.Popen(
                [
                    "yt-dlp",
                    "-x",
                    "-o", audio_path,
                    "--no-playlist",
                    "--newline",
                    url,
                ],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True,
            )

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                m = re.search(r'\[download\]\s+([\d.]+)%', line)
                if m:
                    yield sse("progress", {
                        "phase": "download",
                        "percent": float(m.group(1)),
                        "message": line,
                    })
                elif "[ExtractAudio]" in line:
                    yield sse("progress", {
                        "phase": "download",
                        "percent": 100,
                        "message": "Extracting audio...",
                    })

            proc.wait()
            if proc.returncode != 0:
                yield sse("error", {"message": "yt-dlp failed"})
                return

            downloaded = [f for f in os.listdir(tmp_dir) if f.startswith("audio.")]
            if not downloaded:
                yield sse("error", {"message": "Download produced no audio file"})
                return

            audio_file = os.path.join(tmp_dir, downloaded[0])

            # --- Phase 2: Transcribe with real-time segment streaming ---
            # Get duration via ffprobe (reads header only, no file loading)
            duration = 0
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "csv=p=0", audio_file],
                    capture_output=True, text=True, timeout=5,
                )
                duration = float(probe.stdout.strip())
            except Exception:
                pass

            if duration > 0:
                mins = int(duration // 60)
                secs = int(duration % 60)
                yield sse("progress", {
                    "phase": "transcribe",
                    "message": f"Transcribing ({mins}m {secs}s)...",
                })
            else:
                yield sse("progress", {"phase": "transcribe", "message": "Transcribing..."})

            segments, _ = model.transcribe(
                audio_file, task="transcribe", language="en",
                beam_size=1, vad_filter=True,
            )
            print(f"[*] English-only transcription")

            yield sse("progress", {"phase": "transcribe", "message": "Transcribing — first segment incoming..."})

            full_text_parts = []
            seg_count = 0
            for seg in segments:
                text_part = seg.text.strip()
                seg_end = seg.end
                percent = round((seg_end / duration) * 100, 1) if duration > 0 else 0
                percent = min(percent, 100)

                if text_part:
                    full_text_parts.append(text_part)

                yield sse("segment", {
                    "text": text_part,
                    "index": seg_count,
                    "percent": percent,
                    "start": round(seg.start, 1),
                    "end": round(seg_end, 1),
                })
                seg_count += 1
                print(f"[*] Segment {seg_count}: {round(seg.start,1)}s-{round(seg_end,1)}s ({percent}%)")

            full_text = " ".join(full_text_parts)

            # --- Phase 3: Save ---
            yield sse("progress", {"phase": "save", "message": "Saving transcript..."})
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"youtube_{timestamp}.txt"
            filepath = os.path.join(SAVE_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Source: {url}\n\n{full_text}")

            yield sse("done", {"text": full_text, "file": filename})

        except Exception as e:
            print(f"[!] YouTube transcription error: {e}")
            yield sse("error", {"message": str(e)})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return Response(stream_with_context(generate()), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,PUT,POST,DELETE,OPTIONS',
    })


@app.route('/save', methods=['POST'])
def save_manual():
    """Manual save endpoint for the 'Save' button."""
    data = request.json
    if not data or 'text' not in data:
        return jsonify({"error": "No text provided"}), 400

    filepath = save_to_disk(data['text'])
    return jsonify({"status": "success", "file": os.path.basename(filepath)})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, 'index.html')

@app.route('/')
def serve_index():
    try:
        with open(HTML_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"index.html not found at {HTML_PATH}", 404

if __name__ == '__main__':
    print(f"[+] Scribe Server running at http://127.0.0.1:5000")
    print(f"[+] Transcripts will be saved to: {SAVE_DIR}")
    app.run(port=5000, threaded=True)
