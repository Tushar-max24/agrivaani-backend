from datetime import datetime
import requests
import os

# ==============================
# CONFIG
# ==============================
DATA_GOV_API_KEY = os.environ.get("DATA_GOV_API_KEY")  # Render-safe
DATASET_ID = "9ef84268-d588-465a-a308-a864a43d0070"

_cached_data = []
_last_fetch_time = None

# ==============================
# STATE NORMALIZER
# ==============================
def normalize_state_name(state: str) -> str:
    state_mapping = {
        "tamilnadu": "Tamil Nadu",
        "tamil nadu": "Tamil Nadu",
        "karnatka": "Karnataka",
        "andhrapradesh": "Andhra Pradesh",
        "andhra pradesh": "Andhra Pradesh",
        "westbengal": "West Bengal",
        "west bengal": "West Bengal",
        "uttarpradesh": "Uttar Pradesh",
        "uttar pradesh": "Uttar Pradesh",
    }
    return state_mapping.get(state.lower().strip(), state)

# ==============================
# FETCH FROM API
# ==============================
def fetch_govt_prices(state=None, limit=100):
    if not DATA_GOV_API_KEY:
        print("❌ DATA_GOV_API_KEY NOT SET")
        return []

    url = f"https://api.data.gov.in/resource/{DATASET_ID}"

    params = {
        "api-key": DATA_GOV_API_KEY,
        "format": "json",
        "limit": limit
    }

    if state:
        state = normalize_state_name(state)
        params["filters[state]"] = state

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        records = data.get("records", [])

        govt_prices = []
        for r in records:
            govt_prices.append({
                "crop": r.get("commodity", "Unknown"),
                "price": int(r.get("modal_price", 0)),
                "quantity": "1 Quintal",
                "state": r.get("state"),
                "district": r.get("district"),
                "market": r.get("market"),
                "source": "govt",
            })

        return govt_prices

    except Exception as e:
        print("❌ GOVT API ERROR:", e)
        return []

# ==============================
# CACHE + FALLBACK
# ==============================
def get_cached_govt_data(state=None, limit=100):
    global _cached_data, _last_fetch_time

    now = datetime.now()

    # Refresh every 30 minutes OR if state filter applied
    if (
        _last_fetch_time is None
        or (now - _last_fetch_time).seconds > 1800
        or state
    ):
        data = fetch_govt_prices(state=state, limit=limit)

        if data:
            _cached_data = data
            _last_fetch_time = now
        else:
            print("⚠️ Using fallback data")

    # Fallback dummy data
    if not _cached_data:
        return [
            {
                "crop": "Rice",
                "price": 2200,
                "quantity": "1 Quintal",
                "state": state or "Tamil Nadu",
                "district": "Local Market",
                "market": "AgriVaani Demo",
                "source": "fallback"
            }
        ]

    return _cached_data
