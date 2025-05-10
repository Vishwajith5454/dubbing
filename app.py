# app.py
import os, uuid, subprocess
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static')
os.makedirs('static/dubbed', exist_ok=True)
os.makedirs('tmp', exist_ok=True)

@app.route('/')
def home():
    return '🎙️ YouTube Dubbing Backend is alive!'

# (Paste your full /api/detect_gender and /api/dub endpoints here)

if __name__ == '__main__':
    # Only used if you ever run `python app.py` locally
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)))

