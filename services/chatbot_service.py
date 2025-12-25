# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import google.generativeai as genai
from translate import Translator
from services.chatbot_state import chat_sessions

# ---------------------------------
# 🔑 LOAD ENV VARIABLES
# ---------------------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not set")

# ---------------------------------
# 🤖 GEMINI CONFIG (CORRECT WAY)
# ---------------------------------
genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "models/gemini-1.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

# ---------------------------------
# 🌍 TRANSLATION (RENAMED SAFELY)
# ---------------------------------
def translate_text(text: str, target_lang: str = "en") -> str:
    if not text or target_lang == "en":
        return text

    try:
        translator = Translator(to_lang=target_lang)
        chunk_size = 400
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

        translated_chunks = []
        for chunk in chunks:
            try:
                translated_chunks.append(translator.translate(chunk))
            except:
                translated_chunks.append(chunk)

        return " ".join(translated_chunks)

    except Exception as e:
        print("Translation error:", e)
        return text

# ---------------------------------
# 🧠 SLOT DEFINITIONS
# ---------------------------------
REQUIRED_SLOTS = ["location", "crop", "stage"]

QUESTIONS = {
    "location": "Please tell your location (District / State).",
    "crop": "Which crop are you growing?",
    "stage": "What is the crop stage? (sowing / tillering / flowering)"
}

FOLLOW_UP_PROMPT = (
    "You can ask follow-up questions about {crop} in {location} "
    "at {stage} stage, or type 'reset' to start over."
)

# ---------------------------------
# 🌾 GENERATE FARMING ADVICE
# ---------------------------------
def generate_advice(slots: dict) -> dict:
    try:
        prompt = f"""
        You are AgriVaani, an agriculture assistant for Indian farmers.
        Give short, clear, and practical advice.

        Crop: {slots['crop']}
        Location: {slots['location']}
        Stage: {slots['stage']}
        """

        response = model.generate_content(prompt)

        return {
            "message": response.text.strip(),
            "is_error": False
        }

    except Exception as e:
        return {
            "message": "I'm having trouble generating advice right now.",
            "is_error": True
        }

# ---------------------------------
# 💬 CHAT HANDLER
# ---------------------------------
def handle_chatbot_message(session_id: str, message: str, language: str = "en"):
    message = message.strip()
    if not message:
        return {"reply": "Please enter a valid message.", "done": False}

    if message.lower() == "reset":
        chat_sessions.pop(session_id, None)

    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "current_slot": "location",
            "data": {},
            "language": language,
            "active": False
        }
        return {
            "reply": translate_text(QUESTIONS["location"], language),
            "done": False
        }

    session = chat_sessions[session_id]
    slot = session["current_slot"]
    session["data"][slot] = message

    idx = REQUIRED_SLOTS.index(slot)

    if idx < len(REQUIRED_SLOTS) - 1:
        session["current_slot"] = REQUIRED_SLOTS[idx + 1]
        return {
            "reply": translate_text(QUESTIONS[session["current_slot"]], language),
            "done": False
        }

    advice = generate_advice(session["data"])
    reply = advice["message"]

    if language != "en":
        reply = translate_text(reply, language)

    follow_up = translate_text(
        FOLLOW_UP_PROMPT.format(**session["data"]),
        language
    )

    return {
        "reply": f"{reply}\n\n{follow_up}",
        "done": False
    }
