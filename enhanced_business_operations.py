import json
import logging
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, time
import pytz
from sqlalchemy.orm import Session
from database_models import get_db, Customer, Restaurant, create_tables
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Enhanced Restaurant Business Operations API",
    version="2.0.0",
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

# Initialize database tables on startup
@app.on_event("startup")
async def startup_event():
    create_tables()
    logger.info("Database tables created/verified")

# --- PYDANTIC MODELS ---

class BusinessCheckRequest(BaseModel):
    """Request for business hours check with optional customer lookup"""
    phone_number: Optional[str] = None
    restaurant_id: str

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
    
    # Restaurant information
    restaurant_name: str
    restaurant_address: str
    restaurant_phone: str
    website: str
    doordash_link: str
    reservation_message: str
    
    # Additional context
    business_hours_message: str
    lunch_hours_message: str
    greeting_context: str  # "new_customer" or "returning_customer"

# --- HELPER FUNCTIONS ---

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
        # If customer has a preferred time, use it
        return preferred_time
    
    # Default logic: ASAP during business hours, otherwise next available time
    # For now, return "20-25 minutes" as default
    from datetime import timedelta
    pickup_dt = current_time + timedelta(minutes=22)
    return pickup_dt.strftime("%I:%M %p")

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

def check_time_in_periods(current_time: time, periods: List[Dict]) -> bool:
    """Check if current time is within any of the given periods"""
    for period in periods:
        if time_in_range(current_time, period["open_time"], period["close_time"]):
            return True
    return False

def format_business_hours(periods: List[Dict]) -> str:
    """Format business hours for voice response"""
    if not periods:
        return "closed"
    
    hours_parts = []
    for period in periods:
        start = datetime.strptime(period["open_time"], "%H:%M").strftime("%I:%M %p").lstrip('0')
        end = datetime.strptime(period["close_time"], "%H:%M").strftime("%I:%M %p").lstrip('0')
        hours_parts.append(f"{start} to {end}")
    
    return " and ".join(hours_parts)

async def lookup_or_create_customer(phone_number: str, db: Session) -> Customer:
    """Look up existing customer or create new one"""
    # Clean phone number (remove non-digits)
    clean_phone = ''.join(filter(str.isdigit, phone_number))
    
    # Try to find existing customer
    customer = db.query(Customer).filter(Customer.phone_number == clean_phone).first()
    
    if customer:
        # Update last call time
        customer.last_call_at = datetime.utcnow()
        db.commit()
        return customer
    else:
        # Create new customer
        new_customer = Customer(
            phone_number=clean_phone,
            last_call_at=datetime.utcnow()
        )
        db.add(new_customer)
        db.commit()
        db.refresh(new_customer)
        return new_customer

async def get_restaurant_info(restaurant_id: str, db: Session) -> Restaurant:
    """Get restaurant information from database"""
    restaurant = db.query(Restaurant).filter(Restaurant.id == int(restaurant_id)).first()
    
    if not restaurant:
        # Create default restaurant if not exists (for migration period)
        default_restaurant = Restaurant(
            id=int(restaurant_id),
            name="Umai Nori",
            address="1147 20th Street North West, Washington, DC 20036",
            phone="(202) 262-1073",
            website="www.umainori.com",
            doordash_link="https://order.online/store/umai-nori-washington-29320165/?hideModal=true&pickup=true&redirected=true",
            reservation_link="https://www.opentable.com/restref/client/?rid=1409818",
            timezone="America/New_York",
            business_hours={
                "monday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}, {"open_time": "17:00", "close_time": "22:00"}], "is_closed": False},
                "tuesday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}, {"open_time": "17:00", "close_time": "22:00"}], "is_closed": False},
                "wednesday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}, {"open_time": "17:00", "close_time": "22:00"}], "is_closed": False},
                "thursday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}, {"open_time": "17:00", "close_time": "22:00"}], "is_closed": False},
                "friday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}, {"open_time": "17:00", "close_time": "22:00"}], "is_closed": False},
                "saturday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}, {"open_time": "17:00", "close_time": "22:00"}], "is_closed": False},
                "sunday": {"periods": [{"open_time": "12:00", "close_time": "21:00"}], "is_closed": False}
            },
            lunch_hours={
                "monday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}], "is_closed": False},
                "tuesday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}], "is_closed": False},
                "wednesday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}], "is_closed": False},
                "thursday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}], "is_closed": False},
                "friday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}], "is_closed": False},
                "saturday": {"periods": [{"open_time": "11:00", "close_time": "15:00"}], "is_closed": False},
                "sunday": {"periods": [{"open_time": "12:00", "close_time": "15:00"}], "is_closed": False}
            }
        )
        db.add(default_restaurant)
        db.commit()
        db.refresh(default_restaurant)
        return default_restaurant
    
    return restaurant

# --- API ENDPOINTS ---

@app.get("/")
async def root():
    return {"message": "Enhanced Restaurant Business Operations API with Customer Memory"}

@app.post("/is_in_business_hour", response_model=DynamicVariablesResponse)
async def enhanced_business_check(
    restaurant_id: str = Query(..., description="Restaurant ID"),
    phone_number: Optional[str] = Query(None, description="Customer phone number for lookup"),
    db: Session = Depends(get_db)
):
    """
    Enhanced business hours check that also performs customer lookup
    and returns all dynamic variables needed by Retell AI agent
    """
    try:
        # Get current time
        current_time = get_current_time_eastern()
        current_day = current_time.strftime("%A").lower()
        
        # Get restaurant information
        restaurant = await get_restaurant_info(restaurant_id, db)
        
        # Customer lookup if phone number provided
        customer = None
        customer_name = ""
        customer_phone = phone_number or ""
        greeting_context = "new_customer"
        preferred_pickup = None
        
        if phone_number:
            customer = await lookup_or_create_customer(phone_number, db)
            customer_phone = customer.phone_number
            if customer.name:
                customer_name = customer.name
                greeting_context = "returning_customer"
            preferred_pickup = customer.preferred_pickup_time
        
        # Check business hours
        business_hours_today = restaurant.business_hours.get(current_day, {"is_closed": True})
        is_open = False
        business_message = "We are currently closed."
        
        if not business_hours_today.get("is_closed", True) and "periods" in business_hours_today:
            is_open = check_time_in_periods(current_time.time(), business_hours_today["periods"])
            hours_display = format_business_hours(business_hours_today["periods"])
            if is_open:
                business_message = f"We are currently open. Today's hours: {hours_display}."
            else:
                business_message = f"We are currently closed. Today's hours: {hours_display}."
        
        # Check lunch hours
        lunch_hours_today = restaurant.lunch_hours.get(current_day, {"is_closed": True}) if restaurant.lunch_hours else {"is_closed": True}
        is_lunch = False
        lunch_message = "Lunch service not available."
        
        if not lunch_hours_today.get("is_closed", True) and "periods" in lunch_hours_today:
            is_lunch = check_time_in_periods(current_time.time(), lunch_hours_today["periods"])
            lunch_display = format_business_hours(lunch_hours_today["periods"])
            if is_lunch:
                lunch_message = f"Lunch menu is currently available. Lunch hours: {lunch_display}."
            else:
                lunch_message = f"Lunch menu not currently available. Lunch hours: {lunch_display}."
        
        # Calculate pickup time
        pickup_time = calculate_pickup_time(preferred_pickup)
        
        # Format reservation message
        reservation_message = f"Here's the link to make a reservation at {restaurant.name}: {restaurant.reservation_link}. If the time you're looking for isn't available, feel free to call us back and ask to transfer to a representative."
        
        return DynamicVariablesResponse(
            is_in_business_hour=is_open,
            is_lunch_hour=is_lunch,
            current_eastern_time=format_time_for_voice(current_time),
            pickup_time=pickup_time,
            customer_name=customer_name,
            customer_phone_number=customer_phone,
            restaurant_name=restaurant.name,
            restaurant_address=restaurant.address,
            restaurant_phone=restaurant.phone,
            website=restaurant.website or "",
            doordash_link=restaurant.doordash_link or "",
            reservation_message=reservation_message,
            business_hours_message=business_message,
            lunch_hours_message=lunch_message,
            greeting_context=greeting_context
        )
        
    except Exception as e:
        logger.error(f"Error in enhanced business check: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check business hours and customer info")

@app.post("/update_customer_name")
async def update_customer_name(
    phone_number: str = Query(..., description="Customer phone number"),
    customer_name: str = Query(..., description="Customer name"),
    db: Session = Depends(get_db)
):
    """Update customer name when collected during conversation"""
    try:
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        customer = db.query(Customer).filter(Customer.phone_number == clean_phone).first()
        
        if customer:
            customer.name = customer_name
            customer.updated_at = datetime.utcnow()
            db.commit()
            return {"message": "Customer name updated successfully"}
        else:
            # Create new customer with name
            new_customer = Customer(
                phone_number=clean_phone,
                name=customer_name,
                last_call_at=datetime.utcnow()
            )
            db.add(new_customer)
            db.commit()
            return {"message": "New customer created with name"}
            
    except Exception as e:
        logger.error(f"Error updating customer name: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update customer name")

@app.post("/save_customer_order")
async def save_customer_order(
    phone_number: str = Query(..., description="Customer phone number"),
    restaurant_id: str = Query(..., description="Restaurant ID"),
    order_data: dict = {},
    db: Session = Depends(get_db)
):
    """Save customer order to database"""
    try:
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        customer = await lookup_or_create_customer(clean_phone, db)
        
        # Create order record
        from database_models import Order
        new_order = Order(
            customer_id=customer.id,
            restaurant_id=int(restaurant_id),
            order_data=order_data,
            total_amount=order_data.get("total", 0)
        )
        db.add(new_order)
        db.commit()
        
        return {"message": "Order saved successfully", "order_id": new_order.id}
        
    except Exception as e:
        logger.error(f"Error saving customer order: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save customer order")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002) 