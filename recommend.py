import re
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import pytz
import random

# --- 1. SETUP FASTAPI APP ---
app = FastAPI(title="Restaurant Recommendation API", version="1.0.0")

# --- 2. PYDANTIC MODELS ---
class PriceRange(BaseModel):
    min: float
    max: float

class MenuItem(BaseModel):
    name: str
    price: float
    category: str
    is_lunch_item: bool

class RecommendationRequest(BaseModel):
    menu: List[MenuItem]  # List of pre-parsed menu items
    args: Dict[str, Any]  # Arguments including category and price_range

class RecommendationResponse(BaseModel):
    items: List[MenuItem]

# --- 3. RECOMMENDATION LOGIC ---
def get_recommendations_from_list_thirds(items: list[dict]) -> dict:
    if not items:
        return {"items": []}

    sorted_items = sorted(items, key=lambda x: x['price'])
    n = len(sorted_items)
    
    if n < 3:
        return {"items": random.sample(sorted_items, k=n)}

    third_size = n // 3
    first_third_list = sorted_items[0:third_size]
    second_third_list = sorted_items[third_size : 2 * third_size]
    third_third_list = sorted_items[2 * third_size:]

    recommendations = []

    if first_third_list:
        recommendations.append(random.choice(first_third_list))
    if second_third_list:
        recommendations.append(random.choice(second_third_list))
    if third_third_list:
        recommendations.append(random.choice(third_third_list))
        
    return {"items": recommendations}

# --- 4. API ENDPOINTS ---
@app.get("/")
async def root():
    return {"message": "Restaurant Recommendation API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend(request_data: RecommendationRequest):
    # Extract arguments from request
    args = request_data.args
    category = args.get('category')
    price_range = args.get('price_range')
    
    # Convert Pydantic objects to dicts for processing
    menu_items = [item.dict() for item in request_data.menu]
    
    # Time-based filtering
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    is_lunch_hours = (0 <= now.weekday() <= 4) and (11 <= now.hour < 15)
    
    if is_lunch_hours:
        time_filtered_menu = menu_items
    else:
        time_filtered_menu = [
            item for item in menu_items 
            if not item.get("is_lunch_item", False)
        ]

    # Filter by category
    if category:
        candidate_items = [
            item for item in time_filtered_menu 
            if category.lower() in item['category'].lower()
        ]
    else:
        candidate_items = time_filtered_menu
    
    # Filter by price range
    try:
        min_price = float(price_range['min'])
        max_price = float(price_range['max'])
        candidate_items = [
            item for item in candidate_items 
            if min_price <= item["price"] <= max_price
        ]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=400, 
            detail="Invalid price_range format. Use {'min': number, 'max': number}"
        )

    return get_recommendations_from_list_thirds(candidate_items)

# --- 5. FOR DEPLOYMENT ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)