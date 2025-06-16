import re
import json
import logging
from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks
from pydantic import BaseModel, validator
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import pytz
import random
import google.generativeai as genai
import os
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure cache directory
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
logger.info(f"Cache directory initialized at: {CACHE_DIR.absolute()}")

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable is not set")
    raise ValueError("GEMINI_API_KEY environment variable is not set")

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
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

    class Config:
        json_schema_extra = {
            "properties": {
                "min": {
                    "type": "number",
                    "description": "Minimum price in the range"
                },
                "max": {
                    "type": "number",
                    "description": "Maximum price in the range"
                }
            },
            "required": ["min", "max"]
        }

class MenuItem(BaseModel):
    name: str
    price: float
    category: str
    is_lunch_item: bool

class ArgsModel(BaseModel):
    category: Optional[str] = None
    price_range: PriceRange

    class Config:
        json_schema_extra = {
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category to filter menu items (e.g., 'Appetizers', 'Main Course')"
                },
                "price_range": {
                    "type": "object",
                    "properties": {
                        "min": {
                            "type": "number",
                            "description": "Minimum price in the range"
                        },
                        "max": {
                            "type": "number",
                            "description": "Maximum price in the range"
                        }
                    },
                    "required": ["min", "max"]
                }
            },
            "required": ["price_range"]
        }

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
        # Configure Gemini
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set")
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        logger.info("Successfully configured Gemini API")
        
        # Construct prompt
        prompt = f"""Parse this menu into a JSON array of menu items. Return ONLY the JSON array, no other text or code.

Each item in the array should be an object with these fields:
- name: string (the item name)
- price: number (the price as a number, without the $ symbol)
- category: string (the section name like "Appetizers", "Main Courses", etc.)
- is_lunch_item: boolean (true if it's a lunch special or has a lunch price)
- lunch_price: number or null (if the item has a different lunch price)

Example format:
[
  {{
    "name": "Egg Roll",
    "price": 4.50,
    "category": "Appetizers",
    "is_lunch_item": false,
    "lunch_price": null
  }},
  {{
    "name": "Hunan Shrimp",
    "price": 16.95,
    "category": "Seafood",
    "is_lunch_item": true,
    "lunch_price": 11.95
  }}
]

Menu text:
{menu_text}"""
        
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
        
        # Parse response
        try:
            menu_items = json.loads(response_text)
            logger.info(f"Successfully parsed {len(menu_items)} menu items")
            
            # Log sample items
            if menu_items:
                logger.info("Sample parsed items:")
                for item in menu_items[:3]:
                    logger.info(f"Item: {item.get('name')}, Price: ${item.get('price')}, Category: {item.get('category')}")
            
            return menu_items
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing Gemini response: {str(e)}")
            logger.error(f"Raw response: {response_text}")
            raise
            
    except Exception as e:
        logger.error(f"Error in parse_menu_with_gemini: {str(e)}")
        raise

# --- 5. RECOMMENDATION LOGIC ---
def get_recommendations_from_list_thirds(items: list[dict]) -> dict:
    """
    Takes a list of items, sorts it by price, divides the list into thirds,
    and randomly selects one item from each third.
    """
    if not items:
        return {"items": []}

    # 1. Sort the list of items by price
    sorted_items = sorted(items, key=lambda x: x['price'])
    n = len(sorted_items)
    
    # Handle cases with very few items by returning a random sample
    if n < 3:
        return {"items": random.sample(sorted_items, k=n)}

    # 2. Divide the sorted LIST into three groups by index
    third_size = n // 3
    first_third_list = sorted_items[0:third_size]
    second_third_list = sorted_items[third_size : 2 * third_size]
    third_third_list = sorted_items[2 * third_size:]

    recommendations = []

    # 3. Randomly select one item from each non-empty list group
    if first_third_list:
        recommendations.append(random.choice(first_third_list))
    if second_third_list:
        recommendations.append(random.choice(second_third_list))
    if third_third_list:
        recommendations.append(random.choice(third_third_list))
        
    return {"items": recommendations}

def get_cached_menu(restaurant_id: int) -> Optional[List[Dict]]:
    """Get cached menu for restaurant if it exists."""
    cache_file = CACHE_DIR / f"menu_{restaurant_id}.json"
    logger.info(f"Checking for cached menu at: {cache_file.absolute()}")
    
    try:
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                menu_items = json.load(f)
                logger.info(f"Successfully loaded cached menu with {len(menu_items)} items")
                return menu_items
        else:
            logger.info(f"No cached menu found at {cache_file.absolute()}")
            return None
    except Exception as e:
        logger.error(f"Error reading cache file {cache_file.absolute()}: {str(e)}")
        return None

def cache_menu(restaurant_id: int, menu_items: List[Dict]) -> None:
    """Cache parsed menu items."""
    cache_file = CACHE_DIR / f"menu_{restaurant_id}.json"
    logger.info(f"Attempting to cache menu to: {cache_file.absolute()}")
    
    try:
        # Ensure cache directory exists
        CACHE_DIR.mkdir(exist_ok=True)
        logger.info(f"Cache directory exists at: {CACHE_DIR.absolute()}")
        
        # Write menu items to cache file
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(menu_items, f, indent=2)
        
        # Verify file was written
        if cache_file.exists():
            file_size = cache_file.stat().st_size
            logger.info(f"Successfully cached menu with {len(menu_items)} items. File size: {file_size} bytes")
        else:
            logger.error(f"Cache file was not created at {cache_file.absolute()}")
    except Exception as e:
        logger.error(f"Error caching menu to {cache_file.absolute()}: {str(e)}")
        # Log the full exception details
        import traceback
        logger.error(f"Full error details: {traceback.format_exc()}")

def extract_lunch_hours_with_gemini(menu_text: str) -> Optional[Dict]:
    """Extract lunch hours using Gemini API."""
    try:
        # Configure Gemini API
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
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

def is_within_lunch_hours(current_time: datetime, lunch_hours: Dict) -> bool:
    """Check if current time is within lunch hours."""
    if not lunch_hours or not lunch_hours.get('start') or not lunch_hours.get('end'):
        return False
        
    current_hour = current_time.hour
    current_minute = current_time.minute
    current_time_str = f"{current_hour:02d}:{current_minute:02d}"
    
    return lunch_hours['start'] <= current_time_str <= lunch_hours['end']

def get_price(item: Dict) -> float:
    """Get the appropriate price for an item based on current time."""
    try:
        # Default to dinner price if lunch price is not available
        lunch_price = item.get('lunch_price')
        dinner_price = item.get('price', 0.0)  # Default to 0.0 if price is missing
        
        # If it's a lunch item and we're in lunch hours, use lunch price
        if item.get('is_lunch_item') and is_lunch_hours():
            return float(lunch_price) if lunch_price is not None else dinner_price
        
        return float(dinner_price)
    except (ValueError, TypeError):
        logger.warning(f"Invalid price format for item: {item.get('name', 'Unknown')}")
        return 0.0

# --- 6. API ENDPOINTS ---
@app.get("/")
async def root():
    return {"message": "Restaurant Recommendation API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend(request: Request):
    try:
        # Parse the request body
        body = await request.json()
        logger.info(f"Raw request body: {body}")
        
        # Validate the request structure
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")
        if 'args' not in body:
            raise HTTPException(status_code=400, detail="args is required in request body")
        if not isinstance(body['args'], dict):
            raise HTTPException(status_code=400, detail="args must be a JSON object")
        if 'price_range' not in body['args']:
            raise HTTPException(status_code=400, detail="price_range is required in args")
        
        # Extract and validate price_range
        price_range = body['args']['price_range']
        if isinstance(price_range, str):
            try:
                price_range = json.loads(price_range)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="price_range must be a valid JSON object")
        
        if not isinstance(price_range, dict):
            raise HTTPException(status_code=400, detail="price_range must be a JSON object")
        if 'min' not in price_range or 'max' not in price_range:
            raise HTTPException(status_code=400, detail="price_range must contain min and max values")
        
        try:
            min_price = float(price_range['min'])
            max_price = float(price_range['max'])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="price_range min and max must be numbers")
        
        # Extract category
        category = body['args'].get('category')
        
        # Load menu
        menu_text = get_menu_text(str(1))  # Assuming restaurant_id 1 for now
        if not menu_text:
            raise HTTPException(status_code=404, detail="Menu not found")
        
        # Get cached menu or parse new one
        menu_items = get_cached_menu(1)
        if not menu_items:
            logger.info("Sending menu to Gemini for parsing")
            menu_items = parse_menu_with_gemini(menu_text)
            if menu_items:
                logger.info(f"Parsed {len(menu_items)} menu items")
                cache_menu(1, menu_items)
        
        # Time-based filtering
        tz = pytz.timezone('US/Eastern')
        now = datetime.now(tz)
        is_lunch_hours = (0 <= now.weekday() <= 4) and (11 <= now.hour < 15)
        logger.info(f"Current time: {now}, is_lunch_hours: {is_lunch_hours}")
        
        if is_lunch_hours:
            time_filtered_menu = menu_items
        else:
            time_filtered_menu = [item for item in menu_items if not item.get("is_lunch_item", False)]
        logger.info(f"After time filtering: {len(time_filtered_menu)} items")
        
        # Filter by category first, if provided
        if category:
            candidate_items = [item for item in time_filtered_menu if category.lower() in item['category'].lower()]
            logger.info(f"After category filtering: {len(candidate_items)} items")
        else:
            candidate_items = time_filtered_menu
        
        # Apply price range filter
        logger.info(f"Price range: ${min_price}-${max_price}")
        
        # Log some sample items before price filtering
        if candidate_items:
            logger.info("Sample items before price filtering:")
            for item in candidate_items[:3]:
                logger.info(f"Item: {item.get('name')}, Price: ${item.get('price')}, Category: {item.get('category')}")
        
        candidate_items = [item for item in candidate_items if min_price <= item.get("price", 0) <= max_price]
        logger.info(f"After price filtering: {len(candidate_items)} items")
        
        # Log some sample items after price filtering
        if candidate_items:
            logger.info("Sample items after price filtering:")
            for item in candidate_items[:3]:
                logger.info(f"Item: {item.get('name')}, Price: ${item.get('price')}, Category: {item.get('category')}")
        
        # Pass the final list of candidates to the recommendation logic
        result = get_recommendations_from_list_thirds(candidate_items)
        logger.info(f"Final recommendations: {len(result['items'])} items")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error in recommendation endpoint: {str(e)}\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 7. FOR DEPLOYMENT ---
if __name__ == "__main__":
    ensure_menu_dir()  # Create menus directory if it doesn't exist
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)