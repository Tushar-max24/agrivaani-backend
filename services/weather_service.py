import requests
import random
from typing import Dict, Optional
from services.weather_advisory_service import get_crop_advisory
import os

# OpenWeather API configuration


API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Mock weather data for districts (fallback when API fails)
DISTRICT_WEATHER_DATA = {
    # Southern India
    "coimbatore": {"temp_range": (20, 35), "humidity_range": (50, 85), "rainfall_range": (0, 10)},
    "salem": {"temp_range": (22, 38), "humidity_range": (45, 80), "rainfall_range": (0, 8)},
    "madurai": {"temp_range": (25, 40), "humidity_range": (40, 75), "rainfall_range": (0, 5)},
    "tiruchirapalli": {"temp_range": (24, 39), "humidity_range": (45, 78), "rainfall_range": (0, 7)},
    "tirunelveli": {"temp_range": (26, 38), "humidity_range": (48, 82), "rainfall_range": (0, 6)},
    
    # Northern India
    "ludhiana": {"temp_range": (5, 42), "humidity_range": (30, 85), "rainfall_range": (0, 15)},
    "karnal": {"temp_range": (8, 40), "humidity_range": (35, 88), "rainfall_range": (0, 12)},
    "meerut": {"temp_range": (7, 43), "humidity_range": (32, 82), "rainfall_range": (0, 10)},
    
    # Eastern India
    "kharagpur": {"temp_range": (15, 38), "humidity_range": (50, 90), "rainfall_range": (0, 20)},
    "bhubaneswar": {"temp_range": (18, 36), "humidity_range": (55, 92), "rainfall_range": (0, 25)},
    
    # Western India
    "nashik": {"temp_range": (12, 35), "humidity_range": (40, 85), "rainfall_range": (0, 8)},
    "pune": {"temp_range": (14, 36), "humidity_range": (38, 82), "rainfall_range": (0, 7)},
}

def get_weather(city: str) -> Dict:
    """Get current weather data for a city using OpenWeather API."""
    try:
        params = {
            "q": city,
            "appid": API_KEY,
            "units": "metric"
        }

        response = requests.get(BASE_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return {
                "city": city,
                "temperature": data["main"]["temp"],
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "condition": data["weather"][0]["main"],
                "icon": data["weather"][0]["icon"],
                "advisory": get_crop_advisory(
                    data["main"]["temp"],
                    data["main"]["humidity"],
                    data["weather"][0]["main"]
                )
            }
    except Exception as e:
        print(f"Error fetching weather data: {e}")
    
    # Fallback to mock data if API fails
    return get_mock_weather(city)

def get_district_weather(district: str) -> Dict[str, float]:
    """Get weather data for a district, with fallback to mock data."""
    try:
        # First try to get real data
        weather = get_weather(district)
        if weather and "error" not in weather:
            return {
                "temperature": weather["temperature"],
                "humidity": weather["humidity"],
                "rainfall": float(weather.get("rain", {}).get("1h", 0))  # Rainfall in mm for last hour
            }
    except Exception as e:
        print(f"Error getting district weather: {e}")
    
    # Fallback to mock data
    return get_mock_weather(district)

def get_mock_weather(district: str) -> Dict[str, float]:
    """Generate mock weather data for a district."""
    district_lower = district.lower().strip()
    weather_data = DISTRICT_WEATHER_DATA.get(district_lower, {
        "temp_range": (10, 35),
        "humidity_range": (30, 85),
        "rainfall_range": (0, 5)
    })
    
    # Generate random values within ranges
    temp = round(random.uniform(*weather_data["temp_range"]), 1)
    humidity = random.randint(*weather_data["humidity_range"])
    rainfall = round(random.uniform(*weather_data["rainfall_range"]), 1)
    
    return {
        "temperature": temp,
        "humidity": humidity,
        "rainfall": rainfall,
        "is_mock": True  # Flag to indicate mock data
    }
