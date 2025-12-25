# -*- coding: utf-8 -*-
import os
# from google import genai
import google.generativeai as genai
from services.chatbot_state import chat_sessions
from dotenv import load_dotenv
from translate import Translator

# ---------------------------------
# 🔑 LOAD ENV VARIABLES
# ---------------------------------
load_dotenv()   # Loads .env file variables

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not set in .env file")

# ---------------------------------
# 🤖 GEMINI CLIENT
# ---------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "models/gemini-flash-latest"

def translate(text: str, target_lang: str = "en") -> str:
    """
    Translate text to the target language using the translate package.
    If translation fails or text is None/empty, returns the original text.
    Handles long texts by splitting into chunks.
    """
    if not text or target_lang == "en":
        return text
        
    try:
        # Initialize translator
        translator = Translator(to_lang=target_lang)
        
        # Split text into chunks of 400 characters to avoid length limits
        chunk_size = 400
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        translated_chunks = []
        
        for chunk in chunks:
            if not chunk.strip():
                continue
            try:
                translated = translator.translate(chunk)
                translated_chunks.append(translated)
            except Exception as e:
                print(f"Error translating chunk: {e}")
                translated_chunks.append(chunk)  # Fallback to original chunk
        
        return ' '.join(translated_chunks)
        
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Return original text if translation fails



# ---------------------------------
# 🧠 SLOT DEFINITIONS
# ---------------------------------
REQUIRED_SLOTS = ["location", "crop", "stage"]

QUESTIONS = {
    "location": "Please tell your location (District / State).",
    "crop": "Which crop are you growing?",
    "stage": "What is the crop stage? (sowing / tillering / flowering)"
}

FOLLOW_UP_PROMPT = "You can ask follow-up questions about {crop} in {location} at {stage} stage, or type 'reset' to start over."

# ---------------------------------
# 🌾 GENERATE FARMING ADVICE
# ---------------------------------
def generate_advice(slots: dict) -> dict:
    try:
        # Get the language from the session if available
        language = slots.get('language', 'en')
        language_hint = "in simple English" if language == "en" else f"in simple {language} language"
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[{
                "parts": [{
                    "text": f"""Generate farming advice for {slots['crop']} in {slots['location']} at {slots['stage']} stage. 
                    Keep it concise and practical. You are AgriVaani, an agriculture assistant for Indian farmers. 
                    Respond {language_hint}. Focus on clear, actionable advice suitable for small-scale farmers."""
                }]
            }]
        )
        return {"message": response.text.strip(), "is_error": False}
    except Exception as e:
        error_msg = "I've reached my daily limit for generating farming advice. Please try again tomorrow or upgrade your API plan for more requests." if "429" in str(e) \
                  else "I'm having trouble generating advice right now. Please try again later."
        return {"message": error_msg, "is_error": True}

# ---------------------------------
# 💬 SLOT-BASED CHAT HANDLER
# ---------------------------------
def handle_chatbot_message(session_id: str, message: str, language: str = "en"):
    message = message.strip().lower()
    if not message:
        return {"reply": "Please enter a valid message.", "done": False}

    # Handle reset command
    if message == 'reset':
        if session_id in chat_sessions:
            del chat_sessions[session_id]
        chat_sessions[session_id] = {
            "current_slot": "location",
            "data": {},
            "language": language,
            "conversation_active": False
        }
        return {
            "reply": translate(QUESTIONS["location"], language),
            "done": False
        }

    # 1️⃣ Initialize session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "current_slot": "location",
            "data": {},
            "language": language,
            "conversation_active": False
        }
        return {
            "reply": translate(QUESTIONS["location"], language),
            "done": False
        }

    session = chat_sessions[session_id]
    current_slot = session["current_slot"]
    
    # Update language if changed
    if language != session.get("language"):
        session["language"] = language
        # If this is a language change message, don't process it as a slot value
        if message.startswith("Please respond in"):
            return {
                "reply": translate("Language changed. " + QUESTIONS[current_slot], language),
                "done": False
            }

    # 2️⃣ Save user input (if not a system message)
    if not message.startswith("Please respond in"):
        session["data"][current_slot] = message
    
    # If we just received a language change message, respond with the current question
    if message.startswith("Please respond in"):
        return {
            "reply": translate(QUESTIONS[current_slot], language),
            "done": False
        }

    # 3️⃣ Move to next slot
    slot_index = REQUIRED_SLOTS.index(current_slot)

    if slot_index < len(REQUIRED_SLOTS) - 1:
        next_slot = REQUIRED_SLOTS[slot_index + 1]
        session["current_slot"] = next_slot

        return {
            "reply": translate(QUESTIONS[next_slot], language),
            "done": False
        }

    # 4️⃣ All slots filled → generate advice
    if not session.get("conversation_active"):
        # First time getting all slots filled
        session["data"]["language"] = session.get("language", "en")
        session["conversation_active"] = True
        
        advice_result = generate_advice(session["data"])
        
        # Only translate if it's not an error message and not already in the target language
        if not advice_result.get("is_error", False) and session.get("language") != "en":
            try:
                advice_result["message"] = translate(advice_result["message"], session["language"])
            except Exception as e:
                print(f"Error in final translation: {e}")
                # Keep the English response if translation fails
        
        # Add follow-up prompt
        follow_up = translate(
            FOLLOW_UP_PROMPT.format(
                crop=session["data"]["crop"],
                location=session["data"]["location"],
                stage=session["data"]["stage"]
            ),
            session["language"]
        )
        
        return {
            "reply": f"{advice_result['message']}\n\n{follow_up}",
            "done": False
        }
    else:
        # Handle follow-up question
        try:
            # Add context to the user's question
            context = f"Context: Crop: {session['data']['crop']}, Location: {session['data']['location']}, Stage: {session['data']['stage']}\nQuestion: {message}"
            
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[{
                    "parts": [{
                        "text": f"You are an agriculture assistant. Answer this question based on the context. If the question is not related to farming, politely say you can only help with farming questions.\n\n{context}"
                    }]
                }]
            )
            
            # Add follow-up prompt again
            follow_up = translate(
                FOLLOW_UP_PROMPT.format(
                    crop=session["data"]["crop"],
                    location=session["data"]["location"],
                    stage=session["data"]["stage"]
                ),
                session["language"]
            )
            
            return {
                "reply": f"{response.text.strip()}\n\n{follow_up}",
                "done": False
            }
            
        except Exception as e:
            return {
                "reply": "I'm having trouble processing your question. Please try again or type 'reset' to start over.",
                "done": False
            }
