from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests as http_requests
import base64
import os
import tempfile
import json
import traceback

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

API_KEY = os.environ.get("API_KEY", "sk_zqeef1nk_px9eIdVNTYv7woQrLtCKPUNm")
API_BASE = "https://api.sarvam.ai"

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# ========== DEBUG ENDPOINT ==========
@app.route("/api/debug", methods=["GET"])
def debug():
    """Quick test of API connectivity"""
    tts_resp = http_requests.post(
        f"{API_BASE}/text-to-speech",
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": API_KEY,
        },
        json={
            "text": "Hello test",
            "target_language_code": "en-IN",
            "speaker": "shubh",
            "model": "bulbul:v3",
            "pace": 1.0,
            "speech_sample_rate": "24000",
            "output_audio_codec": "wav",
        },
    )

    chat_resp = http_requests.post(
        f"{API_BASE}/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": API_KEY,
            "Authorization": f"Bearer {API_KEY}",
        },
        json={
            "model": "sarvam-m",
            "messages": [{"role": "user", "content": "Say hello in one sentence"}],
            "temperature": 0.5,
            "max_tokens": 50,
        },
    )

    return jsonify({
        "tts_status": tts_resp.status_code,
        "tts_ok": tts_resp.status_code == 200,
        "tts_error": tts_resp.text[:500] if tts_resp.status_code != 200 else None,
        "chat_status": chat_resp.status_code,
        "chat_ok": chat_resp.status_code == 200,
        "chat_error": chat_resp.text[:500] if chat_resp.status_code != 200 else None,
        "chat_response": chat_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "") if chat_resp.status_code == 200 else None,
    })

# ========== TEXT TO SPEECH ==========
@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    data = request.json
    text = data.get("text", "")
    lang = data.get("language", "en-IN")
    speaker = data.get("speaker", "shubh")

    # Validate speaker name against known valid voices
    valid_speakers = ["shubh", "advait", "amit", "kabir", "ritu", "priya", "neha", "kavya", "shreya"]
    if speaker not in valid_speakers:
        speaker = "priya"  # safe default

    try:
        resp = http_requests.post(
            f"{API_BASE}/text-to-speech",
            headers={
                "Content-Type": "application/json",
                "api-subscription-key": API_KEY,
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
            timeout=30,
        )

        if resp.status_code == 200:
            result = resp.json()
            audio_base64 = result.get("audios", [None])[0]
            return jsonify({"success": True, "audio": audio_base64})
        else:
            print(f"[TTS ERROR] Status: {resp.status_code}, Body: {resp.text[:500]}")
            return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        print(f"[TTS EXCEPTION] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500

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
            resp = http_requests.post(
                f"{API_BASE}/speech-to-text",
                headers={"api-subscription-key": API_KEY},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": model, "language_code": lang},
                timeout=30,
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
            print(f"[STT ERROR] Status: {resp.status_code}, Body: {resp.text[:500]}")
            return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        print(f"[STT EXCEPTION] {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        os.unlink(tmp_path)

# ========== LIVE CONVERSATION ==========
@app.route("/api/conversation", methods=["POST"])
def conversation():
    user_text = None

    if "audio" in request.files:
        audio_file = request.files["audio"]
        lang = request.form.get("language", "hi-IN")
        history_json = request.form.get("history", "[]")
        scenario = request.form.get("scenario", "banking")
        speaker = request.form.get("speaker", "priya")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                stt_resp = http_requests.post(
                    f"{API_BASE}/speech-to-text",
                    headers={"api-subscription-key": API_KEY},
                    files={"file": ("audio.wav", f, "audio/wav")},
                    data={"model": "saarika:v2.5", "language_code": lang},
                    timeout=30,
                )

            if stt_resp.status_code == 200:
                user_text = stt_resp.json().get("transcript", "")
            else:
                print(f"[CONV STT ERROR] {stt_resp.status_code}: {stt_resp.text[:500]}")
                return jsonify({"success": False, "step": "stt", "error": stt_resp.text}), 400
        finally:
            os.unlink(tmp_path)
    else:
        data = request.json or {}
        user_text = data.get("text", "")
        lang = data.get("language", "hi-IN")
        history_json = json.dumps(data.get("history", []))
        scenario = data.get("scenario", "banking")
        speaker = data.get("speaker", "priya")

    if not user_text or not user_text.strip():
        return jsonify({"success": False, "error": "No speech detected. Please try again."}), 400

    # Validate speaker
    valid_speakers = ["shubh", "advait", "amit", "kabir", "ritu", "priya", "neha", "kavya", "shreya"]
    if speaker not in valid_speakers:
        speaker = "priya"

    # Parse conversation history
    try:
        history = json.loads(history_json) if isinstance(history_json, str) else history_json
    except:
        history = []

    # Build messages - ensure first message after system is ALWAYS from user
    system_prompt = get_system_prompt(scenario)
    messages = [{"role": "system", "content": system_prompt}]

    # Defensive: filter history to ensure proper alternation
    # Only include history where user messages come first
    cleaned_history = []
    for h in history:
        if h.get("role") in ("user", "assistant"):
            cleaned_history.append({"role": h["role"], "content": h["content"]})

    # Remove any leading assistant messages
    while cleaned_history and cleaned_history[0]["role"] == "assistant":
        cleaned_history.pop(0)

    for h in cleaned_history:
        messages.append(h)

    # Add current user message
    messages.append({"role": "user", "content": user_text})

    print(f"[CHAT] Sending {len(messages)} messages to Chat API")
    print(f"[CHAT] Message roles: {[m['role'] for m in messages]}")

    try:
        chat_resp = http_requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "api-subscription-key": API_KEY,
                "Authorization": f"Bearer {API_KEY}",
            },
            json={
                "model": "sarvam-m",
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 200,
            },
            timeout=30,
        )

        if chat_resp.status_code != 200:
            print(f"[CHAT ERROR] {chat_resp.status_code}: {chat_resp.text[:500]}")
            return jsonify({"success": False, "step": "chat", "error": chat_resp.text}), 400

        ai_text = chat_resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[CHAT EXCEPTION] {traceback.format_exc()}")
        return jsonify({"success": False, "step": "chat", "error": str(e)}), 500

    # Text-to-Speech for AI response
    try:
        tts_resp = http_requests.post(
            f"{API_BASE}/text-to-speech",
            headers={
                "Content-Type": "application/json",
                "api-subscription-key": API_KEY,
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
            timeout=30,
        )

        audio_base64 = None
        if tts_resp.status_code == 200:
            audio_base64 = tts_resp.json().get("audios", [None])[0]
        else:
            print(f"[CONV TTS ERROR] {tts_resp.status_code}: {tts_resp.text[:500]}")
    except Exception as e:
        print(f"[CONV TTS EXCEPTION] {traceback.format_exc()}")
        audio_base64 = None

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
    print("\n  Ethinos AI Voice Demo")
    print(f"  Open http://localhost:{port} in your browser\n")
    app.run(host="0.0.0.0", port=port, debug=True)
