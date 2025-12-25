from datetime import datetime
from typing import List, Dict, Optional

# In-memory storage for marketplace data
marketplace_db = []

def add_crop(crop_data: Dict) -> Dict:
    """
    Add a new crop to the marketplace database.
    Expected fields:
    - crop_name: str
    - price_per_kg: float
    - quantity_kg: float
    - location: str
    - contact: str
    - farmer_name: str (optional)
    """
    try:
        # Validate required fields
        required_fields = ['crop_name', 'price_per_kg', 'quantity_kg', 'location', 'contact']
        if not all(field in crop_data for field in required_fields):
            missing = [field for field in required_fields if field not in crop_data]
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
            
        # Create crop object with all required fields
        crop = {
            'id': len(marketplace_db) + 1,
            'crop_name': crop_data['crop_name'].strip(),
            'price_per_kg': float(crop_data['price_per_kg']),
            'quantity_kg': float(crop_data['quantity_kg']),
            'location': crop_data['location'].strip(),
            'contact': crop_data['contact'].strip(),
            'farmer_name': crop_data.get('farmer_name', 'Local Farmer').strip(),
            'timestamp': datetime.now().isoformat(),
            'source': 'user'
        }
        
        marketplace_db.append(crop)
        return {
            'success': True,
            'message': 'Crop added successfully',
            'data': crop
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def get_marketplace_data(state: str = None, limit: int = 100) -> List[Dict]:
    """
    Get marketplace data, optionally filtered by state
    """
    try:
        from govt_market import get_cached_govt_data
        
        # Get government data
        govt_data = get_cached_govt_data(state=state, limit=limit)
        
        # Format user data to match govt data structure
        user_data = []
        for item in marketplace_db:
            # Skip if state filter is provided and doesn't match
            if state and state.lower() not in item['location'].lower():
                continue
                
            user_data.append({
                'crop': item['crop_name'],
                'price': item['price_per_kg'],
                'quantity': f"{item['quantity_kg']} kg",
                'state': item['location'],
                'district': 'Local',
                'market': 'Local Market',
                'source': 'user',
                'contact': item['contact'],
                'farmer_name': item['farmer_name'],
                'timestamp': item['timestamp']
            })
        
        # Combine and sort by timestamp (newest first)
        all_data = govt_data + user_data
        all_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return all_data[:limit]
        
    except Exception as e:
        print(f"Error in get_marketplace_data: {e}")
        # Return sample data if there's an error
        return [{
            'crop': 'Sample Crop',
            'price': 100,
            'quantity': '100 kg',
            'state': state or 'Sample State',
            'district': 'Sample District',
            'market': 'Sample Market',
            'source': 'sample',
            'contact': '9876543210',
            'farmer_name': 'Sample Farmer'
        }]
