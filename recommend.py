import re
import json
import logging
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import pytz
import random
import google.generativeai as genai
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable is not set")
    raise ValueError("GEMINI_API_KEY environment variable is not set")

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    logger.info("Successfully configured Gemini API")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {str(e)}")
    raise ValueError(f"Failed to configure Gemini API: {str(e)}")

# --- 1. SETUP FASTAPI APP ---
app = FastAPI(
    title="Restaurant Recommendation API",
    version="1.0.0",
    # Increase payload size limit to 10MB
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
)

# Configure CORS
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. PYDANTIC MODELS ---
class PriceRange(BaseModel):
    min: float
    max: float

class MenuItem(BaseModel):
    name: str
    price: float
    category: str
    is_lunch_item: bool
    description: Optional[str] = None

class RecommendationRequest(BaseModel):
    args: Dict[str, Any]

class RecommendationResponse(BaseModel):
    items: List[MenuItem]

# --- 3. MENU FILE HANDLING ---
MENU_DIR = Path("menus")

def ensure_menu_dir():
    """Ensure the menus directory exists"""
    MENU_DIR.mkdir(exist_ok=True)

def get_menu_text(restaurant_id: str) -> str:
    """Read menu text from file"""
    menu_file = MENU_DIR / f"{restaurant_id}.txt"
    if not menu_file.exists():
        logger.error(f"Menu file not found: {menu_file}")
        raise HTTPException(
            status_code=404,
            detail=f"Menu not found for restaurant_id: {restaurant_id}"
        )
    try:
        return menu_file.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to read menu file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read menu file: {str(e)}"
        )

def extract_lunch_hours(text: str) -> Tuple[int, int]:
    """Extract lunch hours from menu text"""
    # Look for patterns like "11:00 AM to 3:00 PM" or "11 AM to 3 PM"
    time_pattern = r'(\d{1,2})(?::\d{2})?\s*(?:AM|PM)\s*to\s*(\d{1,2})(?::\d{2})?\s*(?:AM|PM)'
    match = re.search(time_pattern, text, re.IGNORECASE)
    
    if match:
        start_hour = int(match.group(1))
        end_hour = int(match.group(2))
        
        # Convert to 24-hour format
        if "PM" in match.group(0) and start_hour < 12:
            start_hour += 12
        if "PM" in match.group(0) and end_hour < 12:
            end_hour += 12
        if "AM" in match.group(0) and start_hour == 12:
            start_hour = 0
        if "AM" in match.group(0) and end_hour == 12:
            end_hour = 0
            
        return start_hour, end_hour
    
    # Default to 11 AM - 3 PM if no hours found
    return 11, 15

def extract_lunch_days(text: str) -> List[int]:
    """Extract lunch days from menu text (0=Monday, 6=Sunday)"""
    days = []
    if "Monday" in text or "Mon" in text:
        days.append(0)
    if "Tuesday" in text or "Tue" in text:
        days.append(1)
    if "Wednesday" in text or "Wed" in text:
        days.append(2)
    if "Thursday" in text or "Thu" in text:
        days.append(3)
    if "Friday" in text or "Fri" in text:
        days.append(4)
    if "Saturday" in text or "Sat" in text:
        days.append(5)
    if "Sunday" in text or "Sun" in text:
        days.append(6)
    return days if days else [0, 1, 2, 3, 4]  # Default to Mon-Fri if no days found

# --- 4. GEMINI MENU PARSER ---
def parse_menu_with_gemini(text: str) -> list[dict]:
    """Uses Gemini to parse menu text into structured data"""
    try:
        # Extract restaurant info section and menu section
        menu_section = text
        if "##Restaurant Info" in text:
            # Split at the first menu section header after Restaurant Info
            parts = text.split("##Restaurant Info", 1)
            if len(parts) > 1:
                # Find the first ## that starts a menu section
                menu_parts = parts[1].split("##", 1)
                if len(menu_parts) > 1:
                    menu_section = "##" + menu_parts[1]
        
        logger.info("Sending menu to Gemini for parsing")
        prompt = f"""
**Task:** Parse this restaurant menu into structured JSON data. Extract every menu item with:
- name
- price (convert to float)
- category
- is_lunch_item (true ONLY for lunch-specific items)
- description (optional, for any additional info like "spicy" or "vegetarian")

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
      "is_lunch_item": false,
      "description": "Optional description"
    }}
  ]
}}

**Menu to Parse:**
{menu_section}
"""
        try:
            response = model.generate_content(prompt)
            logger.info("Received response from Gemini")
        except Exception as e:
            logger.error(f"Gemini API call failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to call Gemini API: {str(e)}"
            )
        
        try:
            parsed = json.loads(response.text)
            logger.info(f"Successfully parsed {len(parsed.get('menu', []))} menu items")
            return parsed.get("menu", [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {str(e)}")
            logger.error(f"Raw response: {response.text}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse menu: Invalid JSON response from Gemini"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in menu parsing: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Menu parsing failed: {str(e)}"
        )

# --- 5. RECOMMENDATION LOGIC ---
def get_recommendations_from_list_thirds(items: list[dict]) -> dict:
    """Get recommendations by dividing items into thirds and selecting one from each"""
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

# --- 6. API ENDPOINTS ---
@app.get("/")
async def root():
    return {"message": "Restaurant Recommendation API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend(
    request_data: RecommendationRequest,
    restaurant_id: str = Query(..., description="Restaurant identifier to load menu from")
):
    try:
        if not restaurant_id:
            raise HTTPException(
                status_code=400,
                detail="restaurant_id is required as a query parameter"
            )

        # Get menu text from file
        menu_text = get_menu_text(restaurant_id)
        logger.info(f"Loaded menu for restaurant {restaurant_id}")
        
        # Extract lunch hours and days
        lunch_start, lunch_end = extract_lunch_hours(menu_text)
        lunch_days = extract_lunch_days(menu_text)
        logger.info(f"Lunch hours: {lunch_start}:00-{lunch_end}:00, Days: {lunch_days}")
        
        # Parse menu with Gemini
        menu_items = parse_menu_with_gemini(menu_text)
        logger.info(f"Parsed {len(menu_items)} menu items")
        
        # Get current time in EST
        est = pytz.timezone('US/Eastern')
        current_time = datetime.now(est)
        current_hour = current_time.hour
        current_day = current_time.weekday()
        
        # Filter items based on time and criteria
        filtered_items = []
        for item in menu_items:
            # Check if item matches category
            if request_data.args.get('category') and item['category'] != request_data.args['category']:
                continue
                
            # Check if item matches price range
            price_range = request_data.args.get('price_range', {})
            if price_range:
                min_price = price_range.get('min', 0)
                max_price = price_range.get('max', float('inf'))
                if not (min_price <= item['price'] <= max_price):
                    continue
            
            # Check if lunch item is available
            if item['is_lunch_item']:
                if current_day not in lunch_days or not (lunch_start <= current_hour < lunch_end):
                    continue
            
            filtered_items.append(item)
        
        logger.info(f"Found {len(filtered_items)} items matching criteria")
        
        # Get recommendations
        recommendations = get_recommendations_from_list_thirds(filtered_items)
        logger.info(f"Generated {len(recommendations['items'])} recommendations")
        
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in recommendation endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# --- 7. FOR DEPLOYMENT ---
if __name__ == "__main__":
    ensure_menu_dir()  # Create menus directory if it doesn't exist
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)