# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import google.generativeai as genai
from services.chatbot_state import chat_sessions

# ---------------------------------
# 🔑 LOAD ENV VARIABLES
# ---------------------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not set")

# ---------------------------------
# 🤖 GEMINI CONFIG
# ---------------------------------
genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "models/gemini-1.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

# ---------------------------------
# 🧠 SLOT DEFINITIONS
# ---------------------------------
REQUIRED_SLOTS = ["location", "crop", "stage"]

QUESTIONS = {
    "location": {
        "en": "Please tell your location (District / State).",
        "hi": "कृपया अपना स्थान बताएं (जिला / राज्य)।",
        "ta": "தயவுசெய்து உங்கள் இடத்தை கூறுங்கள் (மாவட்டம் / மாநிலம்).",
        "te": "దయచేసి మీ ప్రాంతాన్ని చెప్పండి (జిల్లా / రాష్ట్రం).",
    },
    "crop": {
        "en": "Which crop are you growing?",
        "hi": "आप कौन सी फसल उगा रहे हैं?",
        "ta": "நீங்கள் எந்த பயிரை வளர்க்கிறீர்கள்?",
        "te": "మీరు ఏ పంటను సాగు చేస్తున్నారు?",
    },
    "stage": {
        "en": "What is the crop stage? (sowing / tillering / flowering)",
        "hi": "फसल की अवस्था क्या है? (बुवाई / बढ़वार / फूल अवस्था)",
        "ta": "பயிரின் நிலை என்ன? (விதைப்பு / வளர்ச்சி / மலர்ச்சி)",
        "te": "పంట దశ ఏమిటి? (విత్తనం / పెరుగుదల / పుష్ప దశ)",
    }
}

FOLLOW_UP = {
    "en": "You can ask follow-up questions or type 'reset' to start again.",
    "hi": "आप आगे सवाल पूछ सकते हैं या फिर से शुरू करने के लिए 'reset' लिखें।",
    "ta": "மேலும் கேள்விகள் கேட்கலாம் அல்லது மீண்டும் தொடங்க 'reset' எனத் தட்டச்சு செய்யலாம்.",
    "te": "మీరు మరిన్ని ప్రశ్నలు అడగవచ్చు లేదా మళ్లీ ప్రారంభించడానికి 'reset' టైప్ చేయండి.",
}

# ---------------------------------
# 🌾 GENERATE FARMING ADVICE
# ---------------------------------
def generate_advice(slots: dict, language: str) -> str:
    """
    Gemini generates response DIRECTLY in the required language
    """

    language_rules = {
        "en": "Respond in English.",
        "hi": "केवल हिंदी में उत्तर दें। देवनागरी लिपि का उपयोग करें।",
        "ta": "பதிலை தமிழ் மொழியில் மட்டும் வழங்கவும்.",
        "te": "సమాధానాన్ని తెలుగు భాషలో మాత్రమే ఇవ్వండి.",
    }

    prompt = f"""
You are AgriVaani, an AI agriculture assistant for Indian farmers.

IMPORTANT RULES:
- {language_rules.get(language, "Respond in English")}
- Use simple farmer-friendly words
- Give short, practical advice
- Do NOT mix languages

Crop: {slots['crop']}
Location: {slots['location']}
Crop Stage: {slots['stage']}
"""

    response = model.generate_content(prompt)

    # ✅ UTF-8 safe return
    reply = response.text.strip()
    reply = reply.encode("utf-8").decode("utf-8")

    return reply

# ---------------------------------
# 💬 CHAT HANDLER
# ---------------------------------
def handle_chatbot_message(session_id: str, message: str, language: str = "en"):
    message = message.strip()

    if not message:
        return {"reply": "Please enter a valid message.", "done": False}

    if message.lower() == "reset":
        chat_sessions.pop(session_id, None)

    # 🔹 Start new session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "current_slot": "location",
            "data": {},
            "language": language,
        }
        return {
            "reply": QUESTIONS["location"].get(language, QUESTIONS["location"]["en"]),
            "done": False
        }

    session = chat_sessions[session_id]
    slot = session["current_slot"]
    session["data"][slot] = message

    idx = REQUIRED_SLOTS.index(slot)

    # 🔹 Ask next question
    if idx < len(REQUIRED_SLOTS) - 1:
        session["current_slot"] = REQUIRED_SLOTS[idx + 1]
        next_q = QUESTIONS[session["current_slot"]]
        return {
            "reply": next_q.get(language, next_q["en"]),
            "done": False
        }

    # 🔹 Generate advice
    reply = generate_advice(session["data"], language)

    follow_up = FOLLOW_UP.get(language, FOLLOW_UP["en"])

    return {
        "reply": f"{reply}\n\n{follow_up}",
        "done": False
    }
