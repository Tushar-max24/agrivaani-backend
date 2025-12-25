from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from gradio_client import Client

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
    nitrogen: float
    phosphorus: float
    potassium: float
    temperature: float
    humidity: float
    ph: float
    rainfall: float


class FertilizerRequest(BaseModel):
    crop_type: str
    soil_type: str
    nutrient_deficiency: str


class YieldInput(BaseModel):
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
        result = hf_client.predict(
            data.nitrogen,
            data.phosphorus,
            data.potassium,
            data.temperature,
            data.humidity,
            data.ph,
            data.rainfall,
            fn_index=0
        )
        return {"recommended_crop": result}
    except Exception as e:
        raise HTTPException(500, f"Crop prediction failed: {e}")


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
            fn_index=1   # ⚠️ ensure this matches HF fertilizer function
        )

        return {
            "recommended_fertilizer": result,
            "note": "Apply as per local agriculture guidelines"
        }

    except Exception as e:
        raise HTTPException(500, f"Fertilizer prediction failed: {e}")


# ================================
# 🌾 YIELD PREDICTION
# ================================
@app.post("/predict-yield")
def predict_yield(data: YieldInput):
    try:
        result = hf_client.predict(
            data.rainfall,
            data.fertilizer,
            data.temperature,
            data.land_area,
            fn_index=2
        )

        # ✅ HANDLE LIST OR VALUE
        if isinstance(result, list):
            result = result[0]

        result = float(result)

        return {
            "predicted_yield": round(result, 2),
            "unit": "quintals/hectare"
        }

    except Exception as e:
        raise HTTPException(500, f"Yield prediction failed: {e}")


# ================================
# 🦠 DISEASE DETECTION
# ================================
@app.post("/predict-disease")
async def predict_disease(file: UploadFile = File(...)):
    try:
        result = hf_client.predict(
            file.file,
            fn_index=3
        )
        return {"disease": result}
    except Exception as e:
        raise HTTPException(500, f"Disease detection failed: {e}")


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
from models.marketplace import add_crop

@app.get("/marketplace")
def get_marketplace(state: str, limit: int = 100):
    return get_cached_govt_data(state=state, limit=limit)


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
