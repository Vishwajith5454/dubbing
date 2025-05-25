import os
import tempfile
import subprocess
import yt_dlp
import whisper
import numpy as np
import librosa
from googletrans import Translator
from gtts import gTTS
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ── CONFIG ───────────────────────────────────────────────────────────────
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")
DRIVE_FOLDER_ID      = os.getenv("DRIVE_FOLDER_ID", "your_drive_folder_id")
WHISPER_MODEL        = os.getenv("WHISPER_MODEL", "small")
# Threshold Hz: voices above considered female
GENDER_THRESHOLD_HZ  = float(os.getenv("GENDER_THRESHOLD_HZ", 165.0))
# Language codes supported by gTTS
SUPPORTED_LANGS = {
    "english": "en",
    "hindi":   "hi",
    "tamil":   "ta",
    "telugu":  "te",
    "malayalam": "ml",
    "kannada": "kn",
    "marathi": "mr",
    "bengali": "bn",
    "gujarati": "gu"
}
# ─────────────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Google Drive setup
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/drive.file"]
)
drive_service = build("drive", "v3", credentials=creds)

# Load Whisper model once
model      = whisper.load_model(WHISPER_MODEL)
translator = Translator()


def detect_gender(audio_path):
    y, sr = librosa.load(audio_path, sr=None)
    # estimate fundamental frequency
    f0, voiced_flag, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz('C2'),
        fmax=librosa.note_to_hz('C5')
    )
    median_f0 = np.nanmedian(f0)
    return 'female' if median_f0 and median_f0 > GENDER_THRESHOLD_HZ else 'male'


def modify_pitch(input_path, output_path, gender):
    # shift pitch: female up, male down
    factor = 1.1 if gender=='female' else 0.9
    # asetrate filter to shift pitch
    subprocess.run([
        'ffmpeg', '-y', '-i', input_path,
        '-af', f"asetrate=44100*{factor},aresample=44100",
        output_path
    ], check=True)

@app.route('/dub', methods=['POST'])
def dub_video():
    data       = request.get_json()
    yt_url     = data.get('url')
    lang_name  = data.get('lang', 'english').lower()
    lang_code  = SUPPORTED_LANGS.get(lang_name, 'en')

    with tempfile.TemporaryDirectory() as tmp:
        # 1. Download video
        ydl_opts = {
            'outtmpl': os.path.join(tmp, 'video.%(ext)s'),
            'format': 'bestvideo+bestaudio'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info       = ydl.extract_info(yt_url, download=True)
            video_path = ydl.prepare_filename(info)

        # 2. Extract audio for whisper & gender detect
        audio_path = os.path.join(tmp, 'audio.wav')
        subprocess.run([
            'ffmpeg', '-y', '-i', video_path,
            '-vn', '-ac', '1', '-ar', '16000', audio_path
        ], check=True)

        # 3. Detect gender
        gender = detect_gender(audio_path)

        # 4. Transcribe with Whisper
        result    = model.transcribe(audio_path)
        transcript= result['text']

        # 5. Translate transcript
        translated = translator.translate(transcript, dest=lang_code).text

        # 6. Generate TTS
        tts_raw   = os.path.join(tmp, f'tts_raw_{lang_code}.mp3')
        gTTS(text=translated, lang=lang_code).save(tts_raw)

        # 7. Modify pitch based on detected gender
        tts_mod   = os.path.join(tmp, f'tts_mod_{lang_code}.mp3')
        modify_pitch(tts_raw, tts_mod, gender)

        # 8. Mux modified audio back into video
        dubbed_video = os.path.join(tmp, f'dubbed_{lang_code}.mp4')
        subprocess.run([
            'ffmpeg', '-y', '-i', video_path, '-i', tts_mod,
            '-c:v', 'copy', '-map', '0:v:0', '-map', '1:a:0',
            '-shortest', dubbed_video
        ], check=True)

        # 9. Upload to Google Drive
        metadata = {'name': os.path.basename(dubbed_video), 'parents': [DRIVE_FOLDER_ID]}
        media    = MediaFileUpload(dubbed_video, mimetype='video/mp4')
        file     = drive_service.files().create(
            body=metadata, media_body=media, fields='id, webViewLink'
        ).execute()
        drive_service.permissions().create(
            fileId=file['id'], body={'role':'reader','type':'anyone'}
        ).execute()

        return jsonify({
            'status': 'success',
            'gender_detected': gender,
            'language': lang_name,
            'driveLink': file['webViewLink']
        })

if __name__=='__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
