import json
import logging
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from database_models import Restaurant
from datetime import datetime, time
import pytz
from pathlib import Path

# Database imports
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import os

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

# Database setup
Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./restaurant.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Database models
class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_call_at = Column(DateTime, nullable=True)
    preferred_pickup_time = Column(String(10), nullable=True)
    notes = Column(Text, nullable=True)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

# Data directory for storing business hours
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Default tax rate (6% - individual restaurants can override this)
DEFAULT_TAX_RATE = 0.06

def get_restaurant_tax_rate(restaurant_id: str) -> float:
    """Get the tax rate for a specific restaurant from database"""
    try:
        # First try to get from database
        db = next(get_db())
        # Convert restaurant_id to int for database query
        restaurant_id_int = int(restaurant_id)
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id_int).first()
        if restaurant and restaurant.tax_rate:
            return restaurant.tax_rate
            
        # Fallback to default if restaurant not found
        logger.warning(f"Restaurant {restaurant_id} not found in database, using default tax rate")
        return DEFAULT_TAX_RATE
        
    except Exception as e:
        logger.warning(f"Could not load tax rate for restaurant {restaurant_id} from database: {str(e)}")
        # Fallback to file-based system for backward compatibility
        try:
            store_hours = load_store_hours(restaurant_id)
            return store_hours.tax_rate
        except Exception as e2:
            logger.warning(f"Could not load tax rate from files either: {str(e2)}")
            return DEFAULT_TAX_RATE

# --- PYDANTIC MODELS ---

class TimePeriod(BaseModel):
    """A single time period"""
    open_time: str  # Format: "HH:MM" (24-hour)
    close_time: str  # Format: "HH:MM" (24-hour)

class BusinessHours(BaseModel):
    """Business hours for a specific day"""
    periods: Optional[List[TimePeriod]] = None
    is_closed: bool = False
    
    # Backward compatibility for old format
    open_time: Optional[str] = None
    close_time: Optional[str] = None

class StoreHours(BaseModel):
    """Complete store hours configuration"""
    business_hours: Dict[str, BusinessHours]  # day_of_week -> BusinessHours
    lunch_hours: Optional[Dict[str, BusinessHours]] = None
    timezone: str = "UTC"
    tax_rate: float = 0.06  # Default 6% tax rate

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
    order_notes: str
    customer_phone: str
    tip_amount: float
    customer_name: str
    order_type: str
    order_items: List[OrderItem]
    pick_up_time: Optional[str] = ""
    
    # Optional fields that the tool may or may not send
    customer_address: Optional[str] = None
    execution_message: Optional[str] = None
    
    @field_validator('order_type')
    @classmethod
    def normalize_order_type(cls, v):
        """Normalize order_type to accept both 'pick-up' and 'pick_up' formats"""
        if isinstance(v, str):
            # Convert 'pick-up' to 'pick_up' for consistency
            if v.lower() == 'pick-up':
                return 'pick_up'
            # Also handle other common variations
            elif v.lower() == 'pickup':
                return 'pick_up'
            elif v.lower() == 'dine-in':
                return 'dine_in'
            elif v.lower() == 'dinein':
                return 'dine_in'
        return v

class OrderTotalResponse(BaseModel):
    subtotal: float
    tax_amount: float
    total: float
    item_breakdown: List[Dict[str, Any]]

class DynamicVariablesResponse(BaseModel):
    """Response containing all dynamic variables for Retell"""
    # Business status
    is_in_business_hour: bool
    is_lunch_hour: bool
    
    # Time information
    current_eastern_time: str
    pickup_time: str
    
    # Customer information
    customer_name: str
    customer_phone_number: str
    
    # Additional context
    greeting_context: str  # "new_customer" or "returning_customer"
    business_hours_message: str
    lunch_hours_message: str

# --- HELPER FUNCTIONS ---

def lookup_or_create_customer(db: Session, phone_number: str, customer_name: str = None) -> Customer:
    """Look up existing customer or create new one"""
    # Clean phone number (remove non-digits)
    clean_phone = ''.join(filter(str.isdigit, phone_number))
    
    # Try to find existing customer
    customer = db.query(Customer).filter(Customer.phone_number == clean_phone).first()
    
    if customer:
        # Update last call time and name if provided
        customer.last_call_at = datetime.utcnow()
        if customer_name and customer_name.strip() and not customer.name:
            customer.name = customer_name.strip()
            customer.updated_at = datetime.utcnow()
        db.commit()
        return customer
    else:
        # Create new customer
        new_customer = Customer(
            phone_number=clean_phone,
            name=customer_name.strip() if customer_name and customer_name.strip() else None,
            last_call_at=datetime.utcnow()
        )
        db.add(new_customer)
        db.commit()
        db.refresh(new_customer)
        return new_customer

def get_current_time_eastern() -> datetime:
    """Get current time in Eastern timezone"""
    eastern = pytz.timezone('America/New_York')
    return datetime.now(eastern)

def format_time_for_voice(dt: datetime) -> str:
    """Format time in a voice-friendly way"""
    return dt.strftime("%A, %B %d at %I:%M %p")

def calculate_pickup_time(preferred_time: Optional[str] = None) -> str:
    """Calculate pickup time based on customer preference or default"""
    current_time = get_current_time_eastern()
    
    if preferred_time and preferred_time.upper() != "ASAP":
        return preferred_time
    
    # Default: 20-25 minutes from now
    from datetime import timedelta
    pickup_dt = current_time + timedelta(minutes=22)
    return pickup_dt.strftime("%I:%M %p")

def get_store_hours_file(restaurant_id: str) -> Path:
    """Get the file path for store hours"""
    return DATA_DIR / f"store_hours_{restaurant_id}.json"

def load_store_hours(restaurant_id: str) -> StoreHours:
    """Load store hours from file"""
    file_path = get_store_hours_file(restaurant_id)
    
    if not file_path.exists():
        # Create default hours with split periods (lunch 11-3, dinner 5-10, closed 3-5)
        default_hours = StoreHours(
            business_hours={
                "monday": BusinessHours(periods=[
                    TimePeriod(open_time="11:00", close_time="15:00"),
                    TimePeriod(open_time="17:00", close_time="22:00")
                ]),
                "tuesday": BusinessHours(periods=[
                    TimePeriod(open_time="11:00", close_time="15:00"),
                    TimePeriod(open_time="17:00", close_time="22:00")
                ]),
                "wednesday": BusinessHours(periods=[
                    TimePeriod(open_time="11:00", close_time="15:00"),
                    TimePeriod(open_time="17:00", close_time="22:00")
                ]),
                "thursday": BusinessHours(periods=[
                    TimePeriod(open_time="11:00", close_time="15:00"),
                    TimePeriod(open_time="17:00", close_time="22:00")
                ]),
                "friday": BusinessHours(periods=[
                    TimePeriod(open_time="11:00", close_time="15:00"),
                    TimePeriod(open_time="17:00", close_time="22:00")
                ]),
                "saturday": BusinessHours(periods=[
                    TimePeriod(open_time="11:00", close_time="15:00"),
                    TimePeriod(open_time="17:00", close_time="22:00")
                ]),
                "sunday": BusinessHours(periods=[
                    TimePeriod(open_time="12:00", close_time="21:00")
                ]),
            },
            lunch_hours={
                "monday": BusinessHours(periods=[TimePeriod(open_time="11:00", close_time="15:00")]),
                "tuesday": BusinessHours(periods=[TimePeriod(open_time="11:00", close_time="15:00")]),
                "wednesday": BusinessHours(periods=[TimePeriod(open_time="11:00", close_time="15:00")]),
                "thursday": BusinessHours(periods=[TimePeriod(open_time="11:00", close_time="15:00")]),
                "friday": BusinessHours(periods=[TimePeriod(open_time="11:00", close_time="15:00")]),
                "saturday": BusinessHours(periods=[TimePeriod(open_time="11:00", close_time="15:00")]),
                "sunday": BusinessHours(periods=[TimePeriod(open_time="12:00", close_time="15:00")]),
            },
            timezone="America/New_York",
            tax_rate=0.06  # Default 6% tax rate
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

def is_time_in_business_hours(current_time: time, business_hours: BusinessHours) -> bool:
    """Check if current time is within business hours (supports multiple periods)"""
    if business_hours.is_closed:
        return False
    
    # Handle new format with multiple periods
    if business_hours.periods:
        for period in business_hours.periods:
            if time_in_range(current_time, period.open_time, period.close_time):
                return True
        return False
    
    # Handle old format for backward compatibility
    if business_hours.open_time and business_hours.close_time:
        return time_in_range(current_time, business_hours.open_time, business_hours.close_time)
    
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

@app.get("/debug/endpoints")
async def list_endpoints():
    """Debug endpoint to list all registered routes"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', 'Unknown')
            })
    return {"registered_endpoints": routes}

async def _check_business_hours(restaurant_id: str):
    """Internal function to check business hours"""
    store_hours = load_store_hours(restaurant_id)
    current_time = get_current_time(store_hours.timezone)
    current_day = get_day_name(current_time.weekday())
    
    if current_day not in store_hours.business_hours:
        return {"is_in_business_hour": False, "message": "No business hours configured for this day"}
    
    day_hours = store_hours.business_hours[current_day]
    
    if day_hours.is_closed:
        return {"is_in_business_hour": False, "message": "Restaurant is closed today"}
    
    is_open = is_time_in_business_hours(current_time.time(), day_hours)
    
    # Format business hours display
    if day_hours.periods:
        hours_display = ", ".join([f"{p.open_time} - {p.close_time}" for p in day_hours.periods])
    else:
        hours_display = f"{day_hours.open_time} - {day_hours.close_time}"
    
    return {
        "is_in_business_hour": is_open,
        "current_time": current_time.strftime("%H:%M"),
        "business_hours": hours_display,
        "day": current_day.title()
    }

# Business hour check endpoint moved to main.py to avoid duplicate endpoints

# Update customer name endpoint moved to main.py to avoid duplicate endpoints

async def _check_lunch_hours(restaurant_id: str):
    """Internal function to check lunch hours"""
    store_hours = load_store_hours(restaurant_id)
    current_time = get_current_time(store_hours.timezone)
    current_day = get_day_name(current_time.weekday())
    
    if not store_hours.lunch_hours or current_day not in store_hours.lunch_hours:
        return {"is_in_lunch_hour": False, "message": "No lunch hours configured for this day"}
    
    day_lunch_hours = store_hours.lunch_hours[current_day]
    
    if day_lunch_hours.is_closed:
        return {"is_in_lunch_hour": False, "message": "No lunch service today"}
    
    is_lunch_time = is_time_in_business_hours(current_time.time(), day_lunch_hours)
    
    # Format lunch hours display
    if day_lunch_hours.periods:
        lunch_hours_display = ", ".join([f"{p.open_time} - {p.close_time}" for p in day_lunch_hours.periods])
    else:
        lunch_hours_display = f"{day_lunch_hours.open_time} - {day_lunch_hours.close_time}"
    
    return {
        "is_in_lunch_hour": is_lunch_time,
        "current_time": current_time.strftime("%H:%M"),
        "lunch_hours": lunch_hours_display,
        "day": current_day.title()
    }

# Lunch hour check endpoint moved to main.py to avoid duplicate endpoints

# Order total calculation moved to main.py to avoid duplicate endpoints

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
    uvicorn.run(app, host="0.0.0.0", port=8001)