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
    model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
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

def extract_lunch_hours(menu_text):
    """Extract lunch hours from menu text."""
    try:
        # Look for lunch hours pattern - handle both formats:
        # "from 11:00 AM to 3:00 PM" and "11:00 AM - 3:00 PM"
        lunch_patterns = [
            r"from\s+(\d{1,2}:\d{2}\s*[AaPp][Mm])\s+to\s+(\d{1,2}:\d{2}\s*[AaPp][Mm])",
            r"(\d{1,2}:\d{2}\s*[AaPp][Mm])\s*-\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])"
        ]
        
        for pattern in lunch_patterns:
            match = re.search(pattern, menu_text, re.IGNORECASE)
            if match:
                start_time = match.group(1).strip()
                end_time = match.group(2).strip()
                
                # Convert to 24-hour format
                start_dt = datetime.strptime(start_time, "%I:%M %p")
                end_dt = datetime.strptime(end_time, "%I:%M %p")
                
                # Format as HH:MM
                start_24 = start_dt.strftime("%H:%M")
                end_24 = end_dt.strftime("%H:%M")
                
                # Extract days - look for both formats:
                # "Monday, Tuesday, Wednesday, Thursday, Friday" and "Monday-Friday"
                days_patterns = [
                    r"Monday,\s*Tuesday,\s*Wednesday,\s*Thursday,\s*Friday",
                    r"Monday\s*-\s*Friday"
                ]
                
                days = []
                for days_pattern in days_patterns:
                    if re.search(days_pattern, menu_text, re.IGNORECASE):
                        days = list(range(5))  # 0-4 for Monday-Friday
                        break
                
                logger.info(f"Extracted lunch hours: {start_24}-{end_24}, Days: {days}")
                return {
                    "start": start_24,
                    "end": end_24,
                    "days": days
                }
        
        logger.warning("No lunch hours found in menu text")
        return None
    except Exception as e:
        logger.error(f"Error extracting lunch hours: {str(e)}")
        return None

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
def parse_menu_with_gemini(menu_text: str) -> List[Dict]:
    """Parse menu text using Gemini API."""
    try:
        # Configure Gemini API
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        logger.info("Successfully configured Gemini API")
        
        # Create prompt
        prompt = f"""Parse this menu into a JSON array of items. Each item should have:
- name: string
- price: number
- category: string
- is_lunch_item: boolean
- description: string or null

Menu text:
{menu_text}

Return ONLY the JSON array, no other text or formatting."""

        # Get response from Gemini
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Remove markdown code block if present
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        # Parse JSON response
        try:
            parsed_response = json.loads(response_text)
            if isinstance(parsed_response, dict) and 'menu' in parsed_response:
                menu_items = parsed_response['menu']
            else:
                menu_items = parsed_response
                
            logger.info(f"Successfully parsed {len(menu_items)} menu items")
            return menu_items
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {str(e)}")
            logger.error(f"Raw response: {response_text}")
            raise HTTPException(status_code=500, detail="Failed to parse menu")
            
    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to call Gemini API: {str(e)}")

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

# Add cache directory setup
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

def get_cached_menu(restaurant_id: int) -> Optional[List[Dict]]:
    """Get cached menu for restaurant if it exists."""
    cache_file = CACHE_DIR / f"menu_{restaurant_id}.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading cache: {str(e)}")
    return None

def cache_menu(restaurant_id: int, menu_items: List[Dict]):
    """Cache parsed menu items."""
    cache_file = CACHE_DIR / f"menu_{restaurant_id}.json"
    try:
        with open(cache_file, 'w') as f:
            json.dump(menu_items, f)
    except Exception as e:
        logger.error(f"Error caching menu: {str(e)}")

def extract_lunch_hours_with_gemini(menu_text: str) -> Optional[Dict]:
    """Extract lunch hours using Gemini API."""
    try:
        # Configure Gemini API
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        
        # Create prompt
        prompt = f"""Extract lunch hours and days from this menu text. Return a JSON object with:
- start: time in 24-hour format (HH:MM)
- end: time in 24-hour format (HH:MM)
- days: array of numbers (0=Monday through 6=Sunday)

Example response:
{{
    "start": "11:00",
    "end": "15:00",
    "days": [0, 1, 2, 3, 4]
}}

Menu text:
{menu_text}

Return ONLY the JSON object, no other text or formatting."""

        # Get response from Gemini
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Remove markdown code block if present
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        # Parse JSON response
        try:
            lunch_hours = json.loads(response_text)
            logger.info(f"Extracted lunch hours: {lunch_hours}")
            return lunch_hours
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse lunch hours JSON: {str(e)}")
            logger.error(f"Raw response: {response_text}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting lunch hours with Gemini: {str(e)}")
        return None

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
        
        # Try to get cached menu first
        menu_items = get_cached_menu(int(restaurant_id))
        
        if not menu_items:
            # Extract lunch hours and days using Gemini
            lunch_hours = extract_lunch_hours_with_gemini(menu_text)
            if not lunch_hours:
                logger.warning("Failed to extract lunch hours, defaulting to None")
                lunch_hours = {"start": None, "end": None, "days": []}
            
            logger.info(f"Lunch hours: {lunch_hours}")
            
            # Parse menu with Gemini
            logger.info("Sending menu to Gemini for parsing")
            menu_items = parse_menu_with_gemini(menu_text)
            
            # Cache the parsed menu
            cache_menu(int(restaurant_id), menu_items)
        else:
            logger.info("Using cached menu")
        
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
                if current_day not in lunch_hours['days'] or not (lunch_hours['start'] <= current_hour < lunch_hours['end']):
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