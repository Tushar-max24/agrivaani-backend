# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import google.generativeai as genai
from services.chatbot_state import chat_sessions

# -----------------------------
# LOAD ENV
# -----------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not set")

# -----------------------------
# GEMINI CONFIG
# -----------------------------
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    "models/gemini-1.5-flash",
    generation_config={
        "temperature": 0.6,
        "max_output_tokens": 400,
    }
)

# -----------------------------
# CHAT HANDLER (SAFE)
# -----------------------------
def handle_chatbot_message(session_id: str, message: str, language: str = "en"):
    try:
        message = message.strip()
        if not message:
            return {"reply": "Please type a message.", "done": False}

        # Initialize session
        if session_id not in chat_sessions:
            chat_sessions[session_id] = []

        history = chat_sessions[session_id]

        system_prompt = f"""
You are AgriVaani, an expert AI assistant for Indian farmers.

Rules:
- Reply ONLY in {language}
- Use simple farmer-friendly language
- Give practical agricultural advice
- Ask follow-up questions naturally
"""

        prompt = system_prompt.strip() + "\n\n"

        for turn in history[-5:]:  # limit history
            prompt += f"User: {turn['user']}\n"
            prompt += f"AI: {turn['ai']}\n"

        prompt += f"User: {message}\nAI:"

        # 🔥 SAFE GEMINI CALL
        response = model.generate_content(prompt)

        if not response or not response.text:
            raise ValueError("Empty response from Gemini")

        reply = response.text.strip()

        # Save history
        history.append({"user": message, "ai": reply})

        return {
            "reply": reply,
            "done": False
        }

    except Exception as e:
        print("❌ CHATBOT ERROR:", str(e))

        # Fallback multilingual-safe message
        fallback = {
            "en": "Sorry, I couldn't process that. Please try again.",
            "hi": "माफ़ कीजिए, अभी उत्तर नहीं दे पा रहा हूँ। कृपया दोबारा प्रयास करें।",
            "ta": "மன்னிக்கவும், இப்போது பதிலளிக்க முடியவில்லை. தயவுசெய்து மீண்டும் முயற்சிக்கவும்.",
            "te": "క్షమించండి, ప్రస్తుతం స్పందించలేకపోతున్నాను. దయచేసి మళ్లీ ప్రయత్నించండి.",
            "mr": "माफ करा, सध्या उत्तर देऊ शकत नाही. कृपया पुन्हा प्रयत्न करा.",
            "gu": "માફ કરશો, હાલમાં જવાબ આપી શકતો નથી. કૃપા કરીને ફરી પ્રયાસ કરો.",
            "pa": "ਮਾਫ਼ ਕਰਨਾ, ਇਸ ਸਮੇਂ ਜਵਾਬ ਨਹੀਂ ਦੇ ਸਕਦਾ। ਕਿਰਪਾ ਕਰਕੇ ਮੁੜ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
        }

        return {
            "reply": fallback.get(language, fallback["en"]),
            "done": False
        }
