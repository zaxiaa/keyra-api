import json
import logging
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, time
import pytz
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Restaurant Business Operations API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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

# Data directory for storing business hours
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Tax rate (static 6% for now)
TAX_RATE = 0.06

# --- PYDANTIC MODELS ---

class BusinessHours(BaseModel):
    """Business hours for a specific day"""
    open_time: str  # Format: "HH:MM" (24-hour)
    close_time: str  # Format: "HH:MM" (24-hour)
    is_closed: bool = False

class StoreHours(BaseModel):
    """Complete store hours configuration"""
    business_hours: Dict[str, BusinessHours]  # day_of_week -> BusinessHours
    lunch_hours: Optional[Dict[str, BusinessHours]] = None
    timezone: str = "UTC"

class Modifier(BaseModel):
    modifier_name: str
    modifier_quantity: int
    modifier_price: float

class OrderItem(BaseModel):
    item_name: str
    item_base_price: float
    item_total: Optional[float] = None
    special_instructions: Optional[str] = None
    modifiers: Optional[List[Modifier]] = None
    item_quantity: int

class OrderRequest(BaseModel):
    delivery_fee: float
    customer_address: Optional[str] = None
    execution_message: Optional[str] = None
    order_notes: str
    customer_phone: str
    tip_amount: float
    customer_name: str
    pick_up_time: Optional[str] = None
    order_type: str
    order_items: List[OrderItem]

class OrderTotalResponse(BaseModel):
    subtotal: float
    tax_amount: float
    total: float
    item_breakdown: List[Dict[str, Any]]

# --- HELPER FUNCTIONS ---

def get_store_hours_file(restaurant_id: str) -> Path:
    """Get the file path for store hours"""
    return DATA_DIR / f"store_hours_{restaurant_id}.json"

def load_store_hours(restaurant_id: str) -> StoreHours:
    """Load store hours from file"""
    file_path = get_store_hours_file(restaurant_id)
    
    if not file_path.exists():
        # Create default hours (9 AM - 9 PM, lunch 11 AM - 3 PM)
        default_hours = StoreHours(
            business_hours={
                "monday": BusinessHours(open_time="09:00", close_time="21:00"),
                "tuesday": BusinessHours(open_time="09:00", close_time="21:00"),
                "wednesday": BusinessHours(open_time="09:00", close_time="21:00"),
                "thursday": BusinessHours(open_time="09:00", close_time="21:00"),
                "friday": BusinessHours(open_time="09:00", close_time="21:00"),
                "saturday": BusinessHours(open_time="10:00", close_time="22:00"),
                "sunday": BusinessHours(open_time="10:00", close_time="20:00"),
            },
            lunch_hours={
                "monday": BusinessHours(open_time="11:00", close_time="15:00"),
                "tuesday": BusinessHours(open_time="11:00", close_time="15:00"),
                "wednesday": BusinessHours(open_time="11:00", close_time="15:00"),
                "thursday": BusinessHours(open_time="11:00", close_time="15:00"),
                "friday": BusinessHours(open_time="11:00", close_time="15:00"),
                "saturday": BusinessHours(open_time="11:00", close_time="15:00"),
                "sunday": BusinessHours(is_closed=True, open_time="00:00", close_time="00:00"),
            },
            timezone="America/New_York"
        )
        save_store_hours(restaurant_id, default_hours)
        return default_hours
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return StoreHours(**data)
    except Exception as e:
        logger.error(f"Error loading store hours for restaurant {restaurant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load store hours")

def save_store_hours(restaurant_id: str, store_hours: StoreHours):
    """Save store hours to file"""
    file_path = get_store_hours_file(restaurant_id)
    try:
        with open(file_path, 'w') as f:
            json.dump(store_hours.dict(), f, indent=2)
    except Exception as e:
        logger.error(f"Error saving store hours for restaurant {restaurant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save store hours")

def get_current_time(timezone_str: str) -> datetime:
    """Get current time in the specified timezone"""
    try:
        tz = pytz.timezone(timezone_str)
        return datetime.now(tz)
    except Exception:
        # Fallback to UTC
        return datetime.now(pytz.UTC)

def time_in_range(current_time: time, start_time: str, end_time: str) -> bool:
    """Check if current time is within the specified range"""
    try:
        start = datetime.strptime(start_time, "%H:%M").time()
        end = datetime.strptime(end_time, "%H:%M").time()
        
        if start <= end:
            return start <= current_time <= end
        else:
            # Handle overnight hours (e.g., 22:00 to 02:00)
            return current_time >= start or current_time <= end
    except Exception:
        return False

def get_day_name(weekday: int) -> str:
    """Convert weekday number to day name"""
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return days[weekday]

def calculate_item_total(item: OrderItem) -> float:
    """Calculate total for a single item including modifiers"""
    base_total = item.item_base_price * item.item_quantity
    
    modifier_total = 0
    if item.modifiers:
        for modifier in item.modifiers:
            modifier_total += modifier.modifier_price * modifier.modifier_quantity
    
    return base_total + modifier_total

# --- API ENDPOINTS ---

@app.get("/")
async def root():
    return {"message": "Restaurant Business Operations API"}

@app.get("/is-in-business-hour")
async def is_in_business_hour(restaurant_id: str = Query(..., description="Restaurant ID")):
    """Check if restaurant is currently in business hours"""
    try:
        store_hours = load_store_hours(restaurant_id)
        current_time = get_current_time(store_hours.timezone)
        current_day = get_day_name(current_time.weekday())
        
        if current_day not in store_hours.business_hours:
            return {"is_in_business_hour": False, "message": "No business hours configured for this day"}
        
        day_hours = store_hours.business_hours[current_day]
        
        if day_hours.is_closed:
            return {"is_in_business_hour": False, "message": "Restaurant is closed today"}
        
        is_open = time_in_range(current_time.time(), day_hours.open_time, day_hours.close_time)
        
        return {
            "is_in_business_hour": is_open,
            "current_time": current_time.strftime("%H:%M"),
            "business_hours": f"{day_hours.open_time} - {day_hours.close_time}",
            "day": current_day.title()
        }
        
    except Exception as e:
        logger.error(f"Error checking business hours: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check business hours")

@app.get("/is-in-lunch-hour")
async def is_in_lunch_hour(restaurant_id: str = Query(..., description="Restaurant ID")):
    """Check if restaurant is currently in lunch hours"""
    try:
        store_hours = load_store_hours(restaurant_id)
        current_time = get_current_time(store_hours.timezone)
        current_day = get_day_name(current_time.weekday())
        
        if not store_hours.lunch_hours or current_day not in store_hours.lunch_hours:
            return {"is_in_lunch_hour": False, "message": "No lunch hours configured for this day"}
        
        day_lunch_hours = store_hours.lunch_hours[current_day]
        
        if day_lunch_hours.is_closed:
            return {"is_in_lunch_hour": False, "message": "No lunch service today"}
        
        is_lunch_time = time_in_range(current_time.time(), day_lunch_hours.open_time, day_lunch_hours.close_time)
        
        return {
            "is_in_lunch_hour": is_lunch_time,
            "current_time": current_time.strftime("%H:%M"),
            "lunch_hours": f"{day_lunch_hours.open_time} - {day_lunch_hours.close_time}",
            "day": current_day.title()
        }
        
    except Exception as e:
        logger.error(f"Error checking lunch hours: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check lunch hours")

@app.post("/get-order-total", response_model=OrderTotalResponse)
async def get_order_total(
    order: OrderRequest,
    restaurant_id: str = Query(..., description="Restaurant ID")
):
    """Calculate order total including tax (ignoring delivery fee and tip for now)"""
    try:
        subtotal = 0
        item_breakdown = []
        
        for item in order.order_items:
            item_total = calculate_item_total(item)
            subtotal += item_total
            
            # Create breakdown for this item
            breakdown_item = {
                "item_name": item.item_name,
                "item_quantity": item.item_quantity,
                "item_base_price": item.item_base_price,
                "item_subtotal": item.item_base_price * item.item_quantity,
                "modifier_total": 0,
                "item_total": item_total
            }
            
            # Add modifier details
            if item.modifiers:
                modifiers_detail = []
                modifier_total = 0
                for modifier in item.modifiers:
                    mod_total = modifier.modifier_price * modifier.modifier_quantity
                    modifier_total += mod_total
                    modifiers_detail.append({
                        "name": modifier.modifier_name,
                        "quantity": modifier.modifier_quantity,
                        "unit_price": modifier.modifier_price,
                        "total": mod_total
                    })
                breakdown_item["modifier_total"] = modifier_total
                breakdown_item["modifiers"] = modifiers_detail
            
            item_breakdown.append(breakdown_item)
        
        # Calculate tax (6% static)
        tax_amount = subtotal * TAX_RATE
        total = subtotal + tax_amount
        
        return OrderTotalResponse(
            subtotal=round(subtotal, 2),
            tax_amount=round(tax_amount, 2),
            total=round(total, 2),
            item_breakdown=item_breakdown
        )
        
    except Exception as e:
        logger.error(f"Error calculating order total: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to calculate order total")

# Configuration endpoints for managing store hours

@app.get("/store-hours/{restaurant_id}")
async def get_store_hours(restaurant_id: str):
    """Get store hours configuration"""
    try:
        store_hours = load_store_hours(restaurant_id)
        return store_hours
    except Exception as e:
        logger.error(f"Error getting store hours: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get store hours")

@app.put("/store-hours/{restaurant_id}")
async def update_store_hours(restaurant_id: str, store_hours: StoreHours):
    """Update store hours configuration"""
    try:
        save_store_hours(restaurant_id, store_hours)
        return {"message": "Store hours updated successfully"}
    except Exception as e:
        logger.error(f"Error updating store hours: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update store hours")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)