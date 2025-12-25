# govt_market.py
from datetime import datetime
import requests
import os
from dotenv import load_dotenv

load_dotenv()

DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY")

DATASET_ID = "9ef84268-d588-465a-a308-a864a43d0070"

_cached_data = []
_last_fetch_date = None

def normalize_state_name(state: str) -> str:
    """Normalize state names to match API's expected format."""
    state_mapping = {
        'karnatka': 'Karnataka',
        'mumbai': 'Maharashtra',
        'bombay': 'Maharashtra',
        'delhi': 'NCT of Delhi',
        'tamilnadu': 'Tamil Nadu',
        'westbengal': 'West Bengal',
        'andhrapradesh': 'Andhra Pradesh',
        'arunachalpradesh': 'Arunachal Pradesh',
        'madhyapradesh': 'Madhya Pradesh',
        'uttarpradesh': 'Uttar Pradesh',
        'uttarakhand': 'Uttarakhand',
        'tamil nadu': 'Tamil Nadu',
        'west bengal': 'West Bengal',
        'andhra pradesh': 'Andhra Pradesh',
        'arunachal pradesh': 'Arunachal Pradesh',
        'madhya pradesh': 'Madhya Pradesh',
        'uttar pradesh': 'Uttar Pradesh',
    }
    normalized = state_mapping.get(state.lower().strip(), state)
    return normalized

def fetch_govt_prices(state=None, limit=100):
    if not DATA_GOV_API_KEY or DATA_GOV_API_KEY == "YOUR_DATA_GOV_API_KEY":
        print("⚠️ DATA_GOV_API_KEY is not set or is using the default value")
        # Return sample data for testing
        return [{
            "crop": "Potato",
            "price": 1500,
            "quantity": "100 kg",
            "state": "Uttar Pradesh",
            "district": "Agra",
            "market": "Agra Mandi",
            "source": "sample"
        }]
        
    url = f"https://api.data.gov.in/resource/{DATASET_ID}"
    params = {
        "api-key": DATA_GOV_API_KEY,
        "format": "json",
        "limit": limit,
    }

    if state:
        # Normalize the state name
        state = normalize_state_name(state)
        params["filters[state]"] = state
        print(f"🔍 Fetching data for state: {state}")

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        records = data.get("records", [])
        print(f"📊 Found {len(records)} records")
        
        if not records:
            print(f"⚠️ No data found for state: {state if state else 'all states'}")
            # Return sample data when no records found
            return [{
                "crop": "Rice",
                "price": 2500,
                "quantity": "1 Quintal",
                "state": state or "Tamil Nadu",
                "district": "Sample District",
                "market": "Sample Market",
                "source": "sample"
            }]
        
        govt_prices = []
        for r in records:
            try:
                price = int(float(str(r.get("modal_price", "0").replace(',', '')) or 0))
                if price <= 0:  # Skip invalid prices
                    continue
                    
                govt_prices.append({
                    "crop": r.get("commodity", "Unknown Crop").title(),
                    "price": price,
                    "quantity": "1 Quintal",
                    "state": r.get("state", "").title(),
                    "district": r.get("district", "").title(),
                    "market": r.get("market", "").title(),
                    "source": "govt"
                })
            except (ValueError, AttributeError) as e:
                print(f"⚠️ Error processing record: {e}")
                continue
                
        if not govt_prices:  # If all records were invalid
            return [{
                "crop": "Wheat",
                "price": 2000,
                "quantity": "1 Quintal",
                "state": state or "Punjab",
                "district": "Sample District",
                "market": "Sample Market",
                "source": "sample"
            }]
            
        return govt_prices
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text}")
        
        # Return sample data on error
        return [{
            "crop": "Tomato",
            "price": 1500,
            "quantity": "1 Quintal",
            "state": state or "Karnataka",
            "district": "Sample District",
            "market": "Sample Market",
            "source": "sample"
        }]


def get_cached_govt_data(state=None, limit=100):
    global _cached_data, _last_fetch_date

    today = datetime.now().date()

    if _last_fetch_date != today or state:
        _cached_data = fetch_govt_prices(state=state, limit=limit)
        _last_fetch_date = today

    return _cached_data

