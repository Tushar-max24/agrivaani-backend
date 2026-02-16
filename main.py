from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from gradio_client import Client, handle_file
import pandas as pd
import tempfile
import traceback
import json
from services.chatbot_service import model
from services.chatbot_service import handle_chatbot_message
from services.weather_service import get_weather

# ================================
# APP INITIALIZATION
# ================================
app = FastAPI(title="AgriVaani Backend")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# HUGGING FACE CLIENT (ONE TIME)
# ================================
hf_client = Client("tuss2418/agrivaani-ml")





DEFAULT_TEMP = 30
DEFAULT_HUMIDITY = 70
DEFAULT_MOISTURE = 40


def deficiency_to_npk(deficiency: str):
    if deficiency == "Nitrogen":
        return 10, 50, 50
    elif deficiency == "Phosphorus":
        return 50, 10, 50
    elif deficiency == "Potassium":
        return 50, 50, 10
    else:
        return 40, 40, 40

# ================================
# INPUT SCHEMAS
# ================================
class AutoCropInput(BaseModel):
    district: str
    season: str
    nitrogen: Optional[float] = 90
    phosphorus: Optional[float] = 40
    potassium: Optional[float] = 40
    temperature: Optional[float] = 28
    humidity: Optional[float] = 65
    ph: Optional[float] = 6.5
    rainfall: Optional[float] = 120


class FertilizerRequest(BaseModel):
    crop_type: str
    soil_type: str
    nutrient_deficiency: str


class YieldRequest(BaseModel):
    rainfall: float
    fertilizer: float
    temperature: float
    land_area: float


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    language: str = "en"


class MarketCrop(BaseModel):
    farmer_name: str
    crop_name: str
    price_per_kg: float
    quantity_kg: float
    location: str
    contact: str


class Record(BaseModel):
    module_name: str
    title: str
    data: dict


class Feedback(BaseModel):
    name: str
    message: str
    timestamp: Optional[str] = None


# ================================
# ROOT
# ================================
@app.get("/")
def root():
    return {"message": "AgriVaani Backend Running ✅"}


# ================================
# 🌾 CROP PREDICTION
# ================================
@app.post("/predict-crop")
def predict_crop(data: AutoCropInput):
    try:
        # Use provided values or defaults
        nitrogen = data.nitrogen if data.nitrogen is not None else 90
        phosphorus = data.phosphorus if data.phosphorus is not None else 40
        potassium = data.potassium if data.potassium is not None else 40
        temperature = data.temperature if data.temperature is not None else 28
        humidity = data.humidity if data.humidity is not None else 65
        ph = data.ph if data.ph is not None else 6.5
        rainfall = data.rainfall if data.rainfall is not None else 120
        
        result = hf_client.predict(
            nitrogen,
            phosphorus,
            potassium,
            temperature,
            humidity,
            ph,
            rainfall,
            api_name="/predict_crop"   # ✅ FIXED
        )

        # ✅ SAVE RECORD
        add_record({
            "module_name": "Crop Prediction",
            "title": "Crop Recommended",
            "data": {
                "inputs": data.dict(),
                "result": str(result)
            }
        })

        return {
            "recommended_crop": str(result)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Crop prediction failed: {e}"
        )


# ================================
# 🌱 FERTILIZER RECOMMENDATION
# ================================
@app.post("/predict-fertilizer")
def predict_fertilizer(data: FertilizerRequest):
    try:
        n, p, k = deficiency_to_npk(data.nutrient_deficiency)

        result = hf_client.predict(
            DEFAULT_TEMP,
            DEFAULT_HUMIDITY,
            DEFAULT_MOISTURE,
            data.soil_type,
            data.crop_type,
            n,
            p,
            k,
            api_name="/predict_fertilizer"   # ✅ FIXED
        )


        add_record({
            "module_name": "Fertilizer Recommendation",
            "title": "Fertilizer Suggested",
            "data": {
                "crop": data.crop_type,
                "soil": data.soil_type,
                "fertilizer": str(result)
            }
        })

        return {
            "recommended_fertilizer": str(result),
            "note": "Apply as per local agriculture guidelines"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fertilizer prediction failed: {e}"
        )


# ================================
# 🌾 YIELD PREDICTION
# ================================
@app.post("/predict-yield")
def predict_yield_api(req: YieldRequest):
    try:
        result = hf_client.predict(
            req.rainfall,
            req.fertilizer,
            req.temperature,
            req.land_area,
            api_name="/predict_yield"   # ✅ FIXED
        )

        add_record({
            "module_name": "Yield Prediction",
            "title": "Yield Predicted",
            "data": {
                "inputs": req.dict(),
                "yield": float(result)
            }
        })

        return {
            "predicted_yield": float(result),
            "unit": "tons/acre"
        }
        

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Yield prediction failed: {e}"
        )


# ================================
# 🦠 DISEASE DETECTION
# ================================
@app.post("/predict-disease")
async def predict_disease(file: UploadFile = File(...)):
    try:
        # Read the uploaded file into memory
        image_data = await file.read()
        
        # Create a temporary file with the image data
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name
        
        try:
            # Pass the image data directly to the HF client
            result = hf_client.predict(
                handle_file(tmp_path),  
                api_name="/predict_disease"
            )

            

            

            # Normalize output to string
            if isinstance(result, list) and len(result) > 0:
                disease = str(result[0])
            else:
                disease = str(result)


            add_record({
                "module_name": "Disease Detection",
                "title": "Disease Detected",
                "data": {
                    "disease": disease
                }
            })

            return {
                "success": True,
                "disease": disease
            }
            
        finally:
            # Clean up the temporary file
            import os
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception as e:
                print(f"⚠️ Error cleaning up temp file: {e}")

    except Exception as e:
        error_text = traceback.format_exc()
        print("❌ HF ERROR TRACEBACK:")
        print(error_text)

        return {
            "success": False,
            "error": "HF_CALL_FAILED",
            "details": str(e)
        }



# ================================
# 🧠 CHATBOT
# ================================
from services.chatbot_service import handle_chatbot_message

@app.post("/chatbot")
async def chatbot(req: ChatRequest) -> Response:
    try:
        response_data = handle_chatbot_message(
            session_id=req.session_id,
            message=req.message,
            language=req.language
        )
        # Ensure proper JSON serialization with ensure_ascii=False for non-ASCII characters
        json_str = json.dumps(response_data, ensure_ascii=False)
        return Response(
            content=json_str,
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        error_msg = f"Error processing chat request: {str(e)}"
        print(error_msg)
        return Response(
            content=json.dumps({"error": error_msg}, ensure_ascii=False),
            status_code=500,
            media_type="application/json; charset=utf-8"
        )


# ================================
# 📰 NEWS
# ================================
from services.news_service import get_agri_news

@app.get("/news")
def news():
    return get_agri_news()


# ================================
# 🏪 MARKETPLACE
# ================================
from govt_market import get_cached_govt_data
from models.marketplace import add_crop, get_all_crops

@app.get("/marketplace")
def get_marketplace(state: str, limit: int = 100):
    try:
        govt_data = get_cached_govt_data(state=state, limit=limit)
        farmer_data = get_all_crops()

        return {
            "success": True,
            "count": len(govt_data) + len(farmer_data),
            "data": govt_data + farmer_data
        }

    except Exception as e:
        print("❌ MARKETPLACE ROUTE ERROR:", e)
        raise HTTPException(status_code=500, detail="Marketplace service failed")


@app.post("/marketplace/add")
def add_marketplace_crop(crop: MarketCrop):
    try:
        add_crop(crop.dict())

        add_record({
            "module_name": "Marketplace",
            "title": "Crop Listed for Sale",
            "data": crop.dict()
        })
        
        return {
            "success": True,
            "message": "Crop listed successfully"
        }

    except Exception as e:
        print("❌ ADD CROP ERROR:", e)
        raise HTTPException(status_code=500, detail="Failed to add crop")


# ================================
# 📝 RECORDS
# ================================
from models.records import add_record, get_all_records, get_records_by_module

@app.post("/records")
def create_record(record: Record):
    return add_record(record.dict())


@app.get("/records")
def list_records():
    return get_all_records()


@app.get("/records/{module_name}")
def list_module_records(module_name: str):
    records = get_records_by_module(module_name)
    if not records:
        raise HTTPException(404, "No records found")
    return records


# ================================
# 📝 FEEDBACK
# ================================
from models.feedback import add_feedback, get_feedback

@app.post("/feedback")
def submit_feedback(feedback: Feedback):
    data = feedback.dict()
    data["timestamp"] = datetime.now().isoformat()

    # Save feedback
    add_feedback(data)

    # ✅ SAVE RECORD
    add_record({
        "module_name": "Feedback",
        "title": "Feedback Submitted",
        "data": data
    })

    return {"success": True}


@app.get("/feedback")
def view_feedback():
    return get_feedback()


@app.get("/weather/{city}")
def weather_by_city(city: str):
    try:
        city = city.strip().lower()
        data = get_weather(city)

        if not data:
            raise HTTPException(status_code=404, detail="City not found")

        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weather")
def weather(city: str):
    city = city.strip().lower()
    return get_weather(city)

# ================================
# ❤️ HEALTH
# ================================
@app.get("/health")
def health():
    return {"status": "ok"}



@app.get("/health/gemini")
def gemini_health():
    result = handle_chatbot_message(
        session_id="health",
        message="Reply with only the word OK",
        language="en"
    )
    return {"status": "success", "reply": result["reply"]}

