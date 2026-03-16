import os
import sys
import subprocess
import whisper
import json
from datetime import datetime

def download_audio(url, output_path):
    print(f"[*] Downloading audio from {url}...")
    base_path = os.path.splitext(output_path)[0]
    # Added user-agent and referer to help bypass 403 Forbidden errors
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--referer", "https://www.google.com/",
        "-o", base_path + ".%(ext)s",
        url
    ]
    subprocess.run(cmd, check=True)
    
    final_path = base_path + ".mp3"
    if os.path.exists(final_path):
        return final_path
    return output_path

def transcribe(audio_path, model_name="small"):
    print(f"[*] Loading Whisper model '{model_name}'...")
    model = whisper.load_model(model_name)
    print(f"[*] Transcribing {audio_path} (Bilingual: English + Arabic)...")
    
    # Priming the model with an initial prompt helps with code-switching and Arabic script
    prompt = "This is a research meeting about Quranic studies, Kalima, and HUFD. " \
             "Discussion in English and Arabic. القرآن الكريم، تدبر، هدى، كلمات."
    
    result = model.transcribe(
        audio_path, 
        verbose=False, 
        initial_prompt=prompt,
        task="transcribe"
    )
    return result

def main():
    if len(sys.argv) < 2:
        print("Usage: python transcribe_meeting.py <url_or_local_file>")
        sys.exit(1)

    input_source = sys.argv[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("data/transcripts", exist_ok=True)
    
    audio_file_template = f"data/transcripts/meeting_{timestamp}.mp3"
    
    if input_source.startswith("http"):
        try:
            audio_file = download_audio(input_source, audio_file_template)
        except Exception as e:
            print(f"[!] Download failed: {e}")
            sys.exit(1)
    else:
        audio_file = input_source

    if not os.path.exists(audio_file):
        print(f"[!] Error: Audio file not found: {audio_file}")
        sys.exit(1)

    result = transcribe(audio_file)
    
    transcript_text_path = f"data/transcripts/meeting_{timestamp}.txt"
    transcript_json_path = f"data/transcripts/meeting_{timestamp}.json"

    with open(transcript_text_path, "w", encoding="utf-8") as f:
        f.write(result["text"])
    
    with open(transcript_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[+] Done!")
    print(f"Text: {transcript_text_path}")
    print(f"Full JSON: {transcript_json_path}")

if __name__ == "__main__":
    main()
