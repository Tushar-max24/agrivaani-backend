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
    model_name="models/gemini-1.5-flash",
    generation_config={
        "temperature": 0.6,
        "max_output_tokens": 500,
    }
)

# -----------------------------
# CHAT HANDLER (REAL CHAT)
# -----------------------------
def handle_chatbot_message(session_id: str, message: str, language: str = "en"):
    message = message.strip()

    if not message:
        return {"reply": "Please type something.", "done": False}

    # Create session if not exists
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []

    # System instruction (VERY IMPORTANT)
    system_prompt = f"""
You are AgriVaani, an expert AI assistant for Indian farmers.

Rules:
- Always reply ONLY in {language} language.
- Use simple, farmer-friendly words.
- Give practical agriculture advice.
- Ask follow-up questions naturally if needed.
- Never use English if language is not English.
"""

    # Build conversation history
    history = chat_sessions[session_id]

    prompt = system_prompt + "\n\n"

    for turn in history:
        prompt += f"User: {turn['user']}\n"
        prompt += f"AI: {turn['ai']}\n"

    prompt += f"User: {message}\nAI:"

    # Generate reply
    response = model.generate_content(prompt)
    reply = response.text.strip()

    # Save conversation
    history.append({
        "user": message,
        "ai": reply
    })

    return {
        "reply": reply,
        "done": False
    }
