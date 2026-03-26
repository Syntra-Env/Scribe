import sys
import os
from faster_whisper import WhisperModel
import json
import threading
import time

class StreamingTranscriber:
    def __init__(self, audio_path, output_path):
        self.audio_path = audio_path
        self.output_path = output_path
        self.full_text = ""
        self.segments = []
        self.running = True
    
    def save_progress(self):
        txt_path = self.output_path + ".txt"
        while self.running:
            time.sleep(2)
            if self.full_text:
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(self.full_text)
                print(f"[*] Auto-saved intermediate output ({len(self.full_text)} chars)", flush=True)
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self.full_text)
        with open(self.output_path + ".json", "w", encoding="utf-8") as f:
            json.dump({"text": self.full_text, "segments": self.segments}, f, indent=2, ensure_ascii=False)
        print(f"[+] Final save complete", flush=True)
    
    def transcribe(self):
        print("[*] Loading Whisper model...", flush=True)
        model = WhisperModel("small", device="cpu", compute_type="int8")
        
        print("[*] Transcribing (English mode, will save progress periodically)...", flush=True)
        
        segments, info = model.transcribe(
            self.audio_path,
            language="en",
            task="transcribe"
        )
        
        self.full_text = info.text if hasattr(info, 'text') else ""
        self.segments = []
        for seg in segments:
            self.segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            })
            self.full_text += seg.text
    
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
