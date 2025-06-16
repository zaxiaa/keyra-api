import re
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import pytz
import random
import google.generativeai as genai  # Add Gemini integration
import os

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

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
    menu_text: str  # Accept raw menu text
    args: Dict[str, Any]

class RecommendationResponse(BaseModel):
    items: List[MenuItem]

# --- 3. GEMINI MENU PARSER ---
def parse_menu_with_gemini(text: str) -> list[dict]:
    """Uses Gemini to parse menu text into structured data"""
    prompt = f"""
**Task:** Parse this restaurant menu into structured JSON data. Extract every menu item with:
- name
- price (convert to float)
- category
- is_lunch_item (true ONLY for lunch-specific items)

**Rules:**
1. Track section headers (e.g., "Appetizers", "Lunch Specials") as categories
2. Set is_lunch_item=True if:
   - Category contains "Lunch"
   - Item name has "(Lunch)"
   - Two prices exist (lunch/dinner)
3. For multiple prices, create two items: "Item (Lunch)" and "Item (Dinner)"
4. Split choice items (with "/") into separate items
5. Skip items without prices
6. Output ONLY valid JSON in this format:
{{
  "menu": [
    {{
      "name": "Item Name",
      "price": 12.99,
      "category": "Category",
      "is_lunch_item": false
    }}
  ]
}}

**Menu to Parse:**
{text}
"""
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        parsed = json.loads(response.text)
        return parsed.get("menu", [])
    
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Menu parsing failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Gemini API error: {str(e)}"
        )

# --- 4. RECOMMENDATION LOGIC ---
def get_recommendations_from_list_thirds(items: list[dict]) -> dict:
    """Same as before"""
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

# --- 5. API ENDPOINTS ---
@app.get("/")
async def root():
    return {"message": "Restaurant Recommendation API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend(request_data: RecommendationRequest):
    # Parse menu using Gemini
    parsed_menu = parse_menu_with_gemini(request_data.menu_text)
    
    # Time-based filtering
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    is_lunch_hours = (0 <= now.weekday() <= 4) and (11 <= now.hour < 15)
    
    if is_lunch_hours:
        time_filtered_menu = parsed_menu
    else:
        time_filtered_menu = [
            item for item in parsed_menu 
            if not item.get("is_lunch_item", False)
        ]

    # Extract arguments from request
    args = request_data.args
    category = args.get('category')
    price_range = args.get('price_range')

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
            if min_price <= item.get("price", 0) <= max_price
        ]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=400, 
            detail="Invalid price_range format. Use {'min': number, 'max': number}"
        )

    return get_recommendations_from_list_thirds(candidate_items)

# --- 6. FOR DEPLOYMENT ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)