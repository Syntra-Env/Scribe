import sys
import os
from faster_whisper import WhisperModel

import threading
import time

class StreamingTranscriber:
    def __init__(self, audio_path, output_path):
        self.audio_path = audio_path
        self.output_path = output_path
        self.full_text = ""
        self.segments = []
        self.running = True
        self.last_saved_text = ""
    
    def save_progress(self):
        txt_path = self.output_path + ".txt"
        while self.running:
            time.sleep(1)
            if self.full_text and self.full_text != self.last_saved_text:
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(self.full_text)
                self.last_saved_text = self.full_text
                print(f"[*] Saved ({len(self.full_text)} chars)", flush=True)
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self.full_text)
        print(f"[+] Done! Final: {txt_path}", flush=True)
    
    def transcribe(self):
        print("[*] Loading Whisper model...", flush=True)
        model = WhisperModel("small", device="cpu", compute_type="int8")
        
        print("[*] Transcribing (English mode, will save progress periodically)...", flush=True)
        
        segments, info = model.transcribe(
            self.audio_path,
            language="en",
            task="transcribe"
        )
        
        self.full_text = ""
        self.segments = []
        total_duration = info.duration or 1
        
        for seg in segments:
            self.segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            })
            self.full_text += seg.text
            progress = min(100, (seg.end / total_duration) * 100)
            print(f"\r[*] Progress: {progress:.1f}% ({seg.end:.1f}s / {total_duration:.1f}s)", end="", flush=True)
        
        print(flush=True)
    
    def run(self):
        save_thread = threading.Thread(target=self.save_progress, daemon=True)
        save_thread.start()
        
        try:
            self.transcribe()
        finally:
            self.running = False
            save_thread.join(timeout=5)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: transcribe_stream.py <audio_file> <output_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_path = sys.argv[2]
    
    if not os.path.exists(audio_path):
        print(f"[!] Audio file not found: {audio_path}")
        sys.exit(1)
    
    transcriber = StreamingTranscriber(audio_path, output_path)
    transcriber.run()
