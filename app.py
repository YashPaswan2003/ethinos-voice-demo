from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import base64
import os
import tempfile

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "sk_zqeef1nk_px9eIdVNTYv7woQrLtCKPUNm")
SARVAM_BASE = "https://api.sarvam.ai"

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    data = request.json
    text = data.get("text", "")
    lang = data.get("language", "en-IN")
    speaker = data.get("speaker", "shubh")

    resp = requests.post(
        f"{SARVAM_BASE}/text-to-speech",
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        },
        json={
            "text": text,
            "target_language_code": lang,
            "speaker": speaker,
            "model": "bulbul:v3",
            "pace": 1.0,
            "speech_sample_rate": "24000",
            "output_audio_codec": "wav",
        },
    )

    if resp.status_code == 200:
        result = resp.json()
        audio_base64 = result.get("audios", [None])[0]
        return jsonify({"success": True, "audio": audio_base64})
    else:
        return jsonify({"success": False, "error": resp.text}), resp.status_code

@app.route("/api/stt", methods=["POST"])
def speech_to_text():
    if "audio" not in request.files:
        return jsonify({"success": False, "error": "No audio file"}), 400

    audio_file = request.files["audio"]
    lang = request.form.get("language", "hi-IN")
    model = request.form.get("model", "saarika:v2.5")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                f"{SARVAM_BASE}/speech-to-text",
                headers={"api-subscription-key": SARVAM_API_KEY},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": model, "language_code": lang},
            )

        if resp.status_code == 200:
            result = resp.json()
            return jsonify({
                "success": True,
                "transcript": result.get("transcript", ""),
                "language": result.get("language_code", ""),
                "confidence": result.get("language_probability", 0),
            })
        else:
            return jsonify({"success": False, "error": resp.text}), resp.status_code
    finally:
        os.unlink(tmp_path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n  Ethinos AI Voice Demo")
    print(f"  Open http://localhost:{port} in your browser\n")
    app.run(host="0.0.0.0", port=port, debug=True)
