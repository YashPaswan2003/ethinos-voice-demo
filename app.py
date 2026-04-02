from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import base64
import os
import tempfile
import json

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "sk_zqeef1nk_px9eIdVNTYv7woQrLtCKPUNm")
SARVAM_BASE = "https://api.sarvam.ai"

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# ========== TEXT TO SPEECH ==========
@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    data = request.json
    text = data.get("text", "")
    lang = data.get("language", "en-IN")
    speaker = data.get("speaker", "meera")

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

# ========== SPEECH TO TEXT ==========
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

# ========== LIVE CONVERSATION ==========
@app.route("/api/conversation", methods=["POST"])
def conversation():
    """
    Full pipeline: receive audio -> STT -> Chat LLM -> TTS -> return text + audio
    """
    user_text = None

    if "audio" in request.files:
        audio_file = request.files["audio"]
        lang = request.form.get("language", "hi-IN")
        history_json = request.form.get("history", "[]")
        scenario = request.form.get("scenario", "banking")
        speaker = request.form.get("speaker", "meera")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                stt_resp = requests.post(
                    f"{SARVAM_BASE}/speech-to-text",
                    headers={"api-subscription-key": SARVAM_API_KEY},
                    files={"file": ("audio.wav", f, "audio/wav")},
                    data={"model": "saarika:v2.5", "language_code": lang},
                )

            if stt_resp.status_code == 200:
                user_text = stt_resp.json().get("transcript", "")
            else:
                return jsonify({"success": False, "step": "stt", "error": stt_resp.text}), 400
        finally:
            os.unlink(tmp_path)
    else:
        data = request.json or {}
        user_text = data.get("text", "")
        lang = data.get("language", "hi-IN")
        history_json = json.dumps(data.get("history", []))
        scenario = data.get("scenario", "banking")
        speaker = data.get("speaker", "meera")

    if not user_text or not user_text.strip():
        return jsonify({"success": False, "error": "No speech detected. Please try again."}), 400

    # Parse conversation history
    try:
        history = json.loads(history_json) if isinstance(history_json, str) else history_json
    except:
        history = []

    # Build messages for Chat API
    # IMPORTANT: Sarvam requires first message after system to be from "user"
    # So the greeting is baked into the system prompt, not sent as assistant message
    system_prompt = get_system_prompt(scenario)

    messages = [{"role": "system", "content": system_prompt}]

    # Only add history entries, ensuring first non-system message is from user
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})

    # Add current user message
    messages.append({"role": "user", "content": user_text})

    chat_resp = requests.post(
        f"{SARVAM_BASE}/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        },
        json={
            "model": "sarvam-m",
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 200,
        },
    )

    if chat_resp.status_code != 200:
        return jsonify({"success": False, "step": "chat", "error": chat_resp.text}), 400

    ai_text = chat_resp.json()["choices"][0]["message"]["content"]

    # Text-to-Speech for AI response
    tts_resp = requests.post(
        f"{SARVAM_BASE}/text-to-speech",
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": SARVAM_API_KEY,
        },
        json={
            "text": ai_text,
            "target_language_code": lang,
            "speaker": speaker,
            "model": "bulbul:v3",
            "pace": 1.0,
            "speech_sample_rate": "24000",
            "output_audio_codec": "wav",
        },
    )

    audio_base64 = None
    if tts_resp.status_code == 200:
        audio_base64 = tts_resp.json().get("audios", [None])[0]

    return jsonify({
        "success": True,
        "user_text": user_text,
        "ai_text": ai_text,
        "audio": audio_base64,
    })


def get_system_prompt(scenario):
    base = """Keep responses concise — 1 to 2 sentences max, like a real phone call.
If the customer speaks in Hindi or Hinglish, respond in the same style.
Always be warm and natural. End with a short follow-up question to keep the conversation going.
You have already greeted the customer, so do NOT greet again. Just respond to what they said."""

    prompts = {
        "banking": f"""You are a friendly AI customer service agent for a major Indian bank.
You help with account inquiries, loans, card services, and banking queries.
{base}""",

        "insurance": f"""You are a helpful AI customer service agent for an Indian insurance company.
You assist with policy inquiries, claim status, premium payments, and new policies.
{base}""",

        "ecommerce": f"""You are a friendly AI support agent for an Indian e-commerce platform.
You help with order tracking, returns, refunds, and delivery issues.
{base}""",

        "telecom": f"""You are a cheerful AI customer care agent for an Indian telecom company.
You help with recharge plans, data packs, billing queries, and network issues.
{base}""",
    }
    return prompts.get(scenario, prompts["banking"])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n  Ethinos AI Voice Demo — Live Conversation Mode")
    print(f"  Open http://localhost:{port} in your browser\n")
    app.run(host="0.0.0.0", port=port, debug=True)
