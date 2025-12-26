marketplace_db = []

def add_crop(crop):
    crop["source"] = "farmer"   # ✅ ADD THIS
    marketplace_db.append(crop)
    return {"success": True}

def get_all_crops():
    return marketplace_db
