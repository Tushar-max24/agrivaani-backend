from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import requests

# ================================
# 🔗 HUGGING FACE ML SERVICE
# ================================
HF_BASE_URL = "https://tuss2418-agrivaani-ml.hf.space"

# ================================
# APP INITIALIZATION
# ================================
app = FastAPI(title="AgriVaani Backend (Proxy Mode)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# INPUT SCHEMAS
# ================================
class AutoCropInput(BaseModel):
    district: str
    season: str


class FertilizerInput(BaseModel):
    temperature: float
    humidity: float
    moisture: float
    soil_type: str
    crop_type: str
    nitrogen: float
    phosphorus: float
    potassium: float


class YieldInput(BaseModel):
    district: str
    season: str
    land_area: float
    fertilizer_level: str



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
# 🌾 CROP PREDICTION (HF PROXY)
# ================================
@app.post("/predict-crop")
def predict_crop(data: AutoCropInput):
    try:
        # 1️⃣ Fetch soil & weather
        soil = get_soil_values(data.district, data.season)
        weather = get_district_weather(data.district)

        # 2️⃣ Send to Hugging Face
        r = requests.post(
            f"{HF_BASE_URL}/run/predict_crop",
            json={
                "data": [
                    soil["N"],
                    soil["P"],
                    soil["K"],
                    weather["temperature"],
                    weather["humidity"],
                    soil["ph"],
                    weather["rainfall"]
                ]
            },
            timeout=30
        )
        r.raise_for_status()
        result = r.json()

        return {
            "district": data.district,
            "season": data.season,
            "recommended_crop": result["data"][0],
            "auto_filled": True
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
def predict_fertilizer(data: FertilizerInput):
    try:
        r = requests.post(
            f"{HF_BASE_URL}/run/predict_fertilizer",
            json={
                "data": [
                    data.temperature,
                    data.humidity,
                    data.moisture,
                    data.soil_type,
                    data.crop_type,
                    data.nitrogen,
                    data.phosphorus,
                    data.potassium
                ]
            },
            timeout=30
        )
        result = r.json()
        return {"fertilizer": result["data"][0]}
    except Exception:
        raise HTTPException(500, "Fertilizer service unavailable")


# ================================
# 🌾 YIELD PREDICTION
# ================================
@app.post("/predict-yield")
def predict_yield(data: YieldInput):
    try:
        weather = get_district_weather(data.district)

        fertilizer_map = {
            "low": 50,
            "medium": 100,
            "high": 150
        }

        fertilizer = fertilizer_map.get(
            data.fertilizer_level.lower(), 100
        )

        r = requests.post(
            f"{HF_BASE_URL}/run/predict_yield",
            json={
                "data": [
                    weather["rainfall"],
                    fertilizer,
                    weather["temperature"],
                    data.land_area
                ]
            },
            timeout=30
        )
        r.raise_for_status()
        result = r.json()

        return {
            "predicted_yield": result["data"][0],
            "unit": "quintals/hectare"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Yield prediction failed: {e}"
        )



# ================================
# 🦠 DISEASE DETECTION (IMAGE)
# ================================
@app.post("/predict-disease")
async def predict_disease(file: UploadFile = File(...)):
    try:
        files = {
            "files": (file.filename, file.file, file.content_type),
            "data": (None, [])
        }
        r = requests.post(
            f"{HF_BASE_URL}/run/predict_disease",
            files=files,
            timeout=60
        )
        result = r.json()
        return {"disease": result["data"][0]}
    except Exception:
        raise HTTPException(500, "Disease detection service unavailable")


# ================================
# 🧠 CHATBOT
# ================================
from services.chatbot_service import handle_chatbot_message

@app.post("/chatbot")
def chatbot(req: ChatRequest):
    return handle_chatbot_message(
        session_id=req.session_id,
        message=req.message,
        language=req.language
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
    return get_cached_govt_data(state=state, limit=limit)


@app.get("/marketplace/states")
def get_available_states():
    data = get_cached_govt_data()
    return sorted({item.get("state", "").strip() for item in data if item.get("state")})


@app.post("/marketplace/add")
def add_marketplace_crop(crop: MarketCrop):
    add_crop(crop.dict())
    return {"message": "Crop listed successfully"}


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
    return add_feedback(data)


@app.get("/feedback")
def view_feedback():
    return get_feedback()


# ================================
# ❤️ HEALTH
# ================================
@app.get("/health")
def health():
    return {"status": "ok"}
