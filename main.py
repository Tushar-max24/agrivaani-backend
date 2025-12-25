from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel

# from PIL import Image
# import numpy as np

import pickle
import pandas as pd
from services.weather_service import get_weather, get_district_weather
from services.soil_service import get_soil_values
# from services.chatbot_service import get_multilingual_chatbot_response
from fastapi.responses import JSONResponse
# from services.chatbot_service import get_multilingual_chatbot_response
from services.chatbot_service import handle_chatbot_message
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from services.news_service import get_agri_news
# from models.marketplace import add_crop, get_crops
from services.govt_market_service import fetch_govt_prices
from govt_market import get_cached_govt_data
from admin_market_db import admin_market_data
from models.marketplace import add_crop, get_all_crops
from models.feedback import add_feedback, get_feedback
from models.records import add_record, get_all_records, get_records_by_module
from datetime import datetime
from typing import List, Optional

from services.disease_cnn_service import predict_disease_api

# ✅ Model loaders
from utils.model_loader import (
    load_crop_model,
    load_fertilizer_model,
    load_yield_model,
    # load_disease_model
)

# --------------------------------------------------
# APP INITIALIZATION
# --------------------------------------------------
app = FastAPI(title="AgriVaani ML Backend")

# Allowed origins for CORS
allowed_origins = [
    "http://localhost",  # For local development
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
    "http://192.168.0.103:8000",  # Your local IP
    "http://192.168.0.103",       # Your local IP without port
    "http://192.168.56.1:8000",
    "http://192.168.56.1", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # For file downloads
)

# --------------------------------------------------
# 🔥 LAZY LOADED MODELS (GLOBAL CACHE)
# --------------------------------------------------
crop_model = None
yield_model = None
# disease_model = None
fertilizer_model = None
crop_encoder = None
soil_encoder = None


# --------------------------------------------------
# INPUT SCHEMAS
# --------------------------------------------------
from typing import Optional

class AutoCropInput(BaseModel):
    district: str
    season: str
    advanced: bool = False
    # Optional fields for advanced mode
    nitrogen: Optional[float] = None
    phosphorus: Optional[float] = None
    potassium: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    ph: Optional[float] = None
    rainfall: Optional[float] = None

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
    rainfall: float
    fertilizer: float
    temperature: float
    area: float


CLASS_NAMES = [
    "Tomato_Early_Blight",
    "Tomato_Late_Blight",
    "Tomato_Healthy",
    "Potato_Early_Blight",
    "Potato_Healthy"
]



class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    language: str = "en"    

class CropItem(BaseModel):
    farmer: str
    crop: str
    price: float
    quantity: float    

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

# --------------------------------------------------
# ROOT
# --------------------------------------------------
@app.get("/")
def root():
    return {"message": "AgriVaani ML Backend Running ✅"}

# --------------------------------------------------
# 🧠 MARKETPLACE MERGE LOGIC
# --------------------------------------------------
def merge_market_data(govt, admin):
    merged = {item["crop"]: item for item in govt}

    for item in admin:
        merged[item["crop"]] = item  # admin overrides govt price

    return list(merged.values())    

# --------------------------------------------------
# 🌾 CROP PREDICTION
# --------------------------------------------------
@app.post("/predict-crop")
def predict_crop(data: AutoCropInput):
    global crop_model
    if crop_model is None:
        crop_model = load_crop_model()

    if not data.advanced:
        # Auto-fetch soil and weather data
        soil_data = get_soil_values(data.district, data.season)
        weather_data = get_district_weather(data.district)
        
        input_data = np.array([[  
            soil_data["N"],
            soil_data["P"],
            soil_data["K"],
            weather_data["temperature"],
            weather_data["humidity"],
            soil_data["ph"],
            weather_data["rainfall"]
        ]])
        
        prediction = crop_model.predict(input_data)[0]
        
        return {
            "district": data.district.capitalize(),
            "season": data.season.capitalize(),
            "auto_filled": True,
            "recommended_crop": prediction,
            "confidence_note": "Prediction based on local soil & weather data"
        }
    else:
        # Use manual inputs
        if None in [data.nitrogen, data.phosphorus, data.potassium, 
                   data.temperature, data.humidity, data.ph, data.rainfall]:
            raise HTTPException(
                status_code=400,
                detail="All soil and weather parameters are required in advanced mode"
            )
            
        input_data = np.array([[  
            data.nitrogen,
            data.phosphorus,
            data.potassium,
            data.temperature,
            data.humidity,
            data.ph,
            data.rainfall
        ]])
        
        prediction = crop_model.predict(input_data)[0]
        
        return {
            "district": data.district.capitalize() if data.district else "Unknown",
            "season": data.season.capitalize() if data.season else "Not specified",
            "auto_filled": False,
            "recommended_crop": prediction,
            "confidence_note": "Prediction based on provided soil & weather data"
        }

# --------------------------------------------------
# 🌱 FERTILIZER RECOMMENDATION
# --------------------------------------------------
@app.post("/predict-fertilizer")
def predict_fertilizer(data: FertilizerInput):
    global fertilizer_model, crop_encoder, soil_encoder

    if fertilizer_model is None:
        fertilizer_model, crop_encoder, soil_encoder = load_fertilizer_model()

    # ✅ RULE-BASED FIRST
    if data.nitrogen < 40 and data.phosphorus >= 40 and data.potassium >= 40:
        return {"fertilizer": "Urea"}
    if data.phosphorus < 40 and data.nitrogen >= 40 and data.potassium >= 40:
        return {"fertilizer": "DAP"}
    if data.potassium < 40 and data.nitrogen >= 40 and data.phosphorus >= 40:
        return {"fertilizer": "MOP"}

    crop_encoded = crop_encoder.transform([data.crop_type.title()])[0]
    soil_encoded = soil_encoder.transform([data.soil_type.title()])[0]

    input_data = np.array([[  
        data.temperature,
        data.humidity,
        data.moisture,
        soil_encoded,
        crop_encoded,
        data.nitrogen,
        data.phosphorus,
        data.potassium
    ]])

    prediction = fertilizer_model.predict(input_data)
    return {"fertilizer": prediction[0]}

# --------------------------------------------------
# 🌾 YIELD PREDICTION
# --------------------------------------------------
@app.post("/predict-yield")
def predict_yield(data: dict):
    global yield_model

    if yield_model is None:
        yield_model = load_yield_model()

    # Load encoders and feature order
    encoders = pickle.load(open("models/yield_encoders.pkl", "rb"))
    feature_names = pickle.load(open("models/yield_features.pkl", "rb"))

    # Create full feature dict with defaults
    input_dict = {feature: 0 for feature in feature_names}

    # Fill values from request
    for key, value in data.items():
        if key in encoders:
            input_dict[key] = encoders[key].transform([value])[0]
        else:
            input_dict[key] = value

    # Convert to DataFrame (IMPORTANT)
    input_df = pd.DataFrame([input_dict], columns=feature_names)

    prediction = yield_model.predict(input_df)

    return {
        "predicted_yield": round(float(prediction[0]), 2)
    }

# --------------------------------------------------
# 🦠 DISEASE DETECTION (CNN)
# --------------------------------------------------
# @app.post("/predict-disease")
# async def predict_disease(file: UploadFile = File(...)):
#     global disease_model
#     if disease_model is None:
#         disease_model = load_disease_model()

#     image = Image.open(file.file).convert("RGB")
#     image = image.resize((128, 128))
#     image = np.array(image) / 255.0
#     image = np.expand_dims(image, axis=0)

#     prediction = disease_model.predict(image)
#     class_index = np.argmax(prediction)

#     return {"disease": CLASS_NAMES[class_index]}

@app.post("/predict-disease")
async def predict_disease(file: UploadFile = File(...)):
    try:
        result = predict_disease_api(file.file)
        return result
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Disease prediction service unavailable"}
        )

# --------------------------------------------------
# 🦠 Weather
# --------------------------------------------------
@app.get("/weather/{city}")
def weather(city: str):
    return get_weather(city)


@app.options("/chatbot", response_class=JSONResponse)
async def options_chatbot():
    return JSONResponse(
        content={"status": "ok"},
        media_type="application/json; charset=utf-8"
    )  # Added missing closing parenthesis


@app.post("/chatbot")
def chatbot(req: ChatRequest):
    response = handle_chatbot_message(
        session_id=req.session_id,
        message=req.message,
        language=req.language
    )
    return JSONResponse(
        content=response,
        media_type="application/json; charset=utf-8"
    )


@app.get("/news")
def news():
    return get_agri_news()    



# @app.post("/marketplace/add")
# def add_marketplace_crop(item: CropItem):
#     data = item.dict()
#     data["source"] = "admin"
#     add_crop(data)
#     return {"message": "Crop added successfully"}


@app.get("/marketplace")
def get_marketplace(
    state: str,
    limit: int = 100
):
    """
    Get market data for a specific state.
    
    Args:
        state: The state to get market data for (required)
        limit: Maximum number of results to return (default: 100)
    """
    # Get government data with state filter applied at the source
    return get_cached_govt_data(state=state, limit=limit)

@app.get("/marketplace/states")
def get_available_states():
    """Get list of all available states from the government data source."""
    govt_data = get_cached_govt_data()
    states = set()

    for item in govt_data:
        state = item.get("state")
        if state:
            states.add(state.strip())

    return sorted(list(states))

@app.post("/marketplace/add")
def add_marketplace_crop(crop: MarketCrop):
    add_crop(crop.dict())
    return {"message": "Crop listed successfully"}

@app.get("/marketplace")
def view_marketplace():
    return get_all_crops()

# --------------------------------------------------
# 📝 RECORDS ENDPOINTS
# --------------------------------------------------

@app.post("/records/")
async def create_record(record: Record):
    """
    Save a new record
    
    - **module_name**: Name of the module (e.g., 'Crop Prediction', 'Weather')
    - **title**: Short summary of the record
    - **data**: JSON data containing the record details
    """
    try:
        saved_record = add_record(record.dict())
        return {"status": "success", "data": saved_record}
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": str(e)}
        )

@app.get("/records/", response_model=List[dict])
async def list_all_records():
    """
    Get all records
    
    Returns all records in the system
    """
    return get_all_records()

@app.get("/records/{module_name}", response_model=List[dict])
async def list_module_records(module_name: str):
    """
    Get records for a specific module
    
    - **module_name**: Name of the module to filter by (e.g., 'Crop Prediction')
    """
    records = get_records_by_module(module_name)
    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No records found for module: {module_name}"
        )
    return records

# --------------------------------------------------
# 📝 FEEDBACK ENDPOINTS
# --------------------------------------------------
from datetime import datetime
from pydantic import BaseModel

class Feedback(BaseModel):
    name: str
    message: str
    timestamp: str = None

@app.post("/feedback")
def submit_feedback(feedback: Feedback):
    """
    Submit new feedback
    
    - **name**: Name of the user
    - **message**: Feedback message
    """
    feedback_dict = feedback.dict()
    feedback_dict['timestamp'] = datetime.now().isoformat()
    result = add_feedback(feedback_dict)
    return JSONResponse(content=result, status_code=200)

@app.get("/feedback")
def get_all_feedback():
    """
    Get all feedback entries (for admin use)
    
    Returns all feedback entries in the system
    """
    return get_feedback()


@app.get("/health")
def health():
    return {"status": "ok"}
