#!/usr/bin/env python3
"""
Main FastAPI application that combines business operations and recommendation services
"""

from fastapi import FastAPI, Query, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging
import os

# USAePay imports
import usaepay

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the internal functions directly from business_operations
from business_operations import _check_lunch_hours, load_store_hours, save_store_hours, calculate_item_total
from business_operations import OrderRequest, OrderTotalResponse, StoreHours, get_restaurant_tax_rate, DynamicVariablesResponse
from business_operations import get_db, lookup_or_create_customer, get_current_time_eastern, format_time_for_voice, calculate_pickup_time
from business_operations import get_day_name, is_time_in_business_hours, Customer
from datetime import datetime
from sqlalchemy.orm import Session

# Import database test function
from database_models import test_database_connection

# Import Pydantic for request/response models
from pydantic import BaseModel

# USAePay models
class CreditCardRequest(BaseModel):
    """Request model for USAePay credit card charging"""
    base_charge_amount: float
    credit_card_number: str
    credit_card_cvv: str
    credit_card_zip_code: str
    credit_card_expiration_date: str  # Format: MMYY
    cardholder_name: str  # Required field - customer's full name
    tip_amount: float = 0.0
    billing_street: str = ""

class CreditCardResponse(BaseModel):
    """Response model for USAePay credit card charging"""
    success: bool
    transaction_id: Optional[str] = None
    auth_code: Optional[str] = None
    result: str
    result_code: str
    total_amount: float
    error_message: Optional[str] = None
    avs_result: Optional[str] = None
    cvv_result: Optional[str] = None

# Twilio SMS models
class SMSRequest(BaseModel):
    """Request model for sending SMS via Twilio"""
    customer_phone: str
    message: str

class SMSResponse(BaseModel):
    """Response model for SMS sending"""
    success: bool
    message_sid: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    phone_number: str

# Place Order models
class PlaceOrderModifier(BaseModel):
    """Modifier item for order placement"""
    modifier_name: str
    modifier_quantity: int
    modifier_price: float

class PlaceOrderItem(BaseModel):
    """Order item for order placement"""
    item_name: str
    item_base_price: float
    special_instructions: Optional[str] = ""
    modifiers: list[PlaceOrderModifier]
    item_quantity: int

class PlaceOrderRequest(BaseModel):
    """Request model for placing an order"""
    customer_address: Optional[str] = ""
    credit_card_number: Optional[str] = ""
    order_notes: str
    customer_phone: str
    pick_up_time: Optional[str] = ""
    credit_card_zip_code: Optional[str] = ""
    delivery_fee: float
    payment_type: Optional[str] = "cash"
    credit_card_security_code: Optional[str] = ""
    tip_amount: float
    customer_name: str
    credit_card_expiration_date: Optional[str] = ""
    order_type: str
    order_items: list[PlaceOrderItem]

class PlaceOrderResponse(BaseModel):
    """Response model for order placement"""
    success: bool
    order_id: Optional[str] = None
    order_number: Optional[str] = None
    total_amount: float
    payment_status: str
    estimated_pickup_time: Optional[str] = None
    message: str
    error_message: Optional[str] = None
    transaction_id: Optional[str] = None

# Create main FastAPI app
app = FastAPI(
    title="Keyra Restaurant API",
    description="Combined API for restaurant business operations and recommendations with customer memory",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Main API root endpoint"""
    return {
        "message": "Keyra Restaurant API with Customer Memory",
        "services": {
            "business_operations": "Business hours, lunch hours, order totals, store configuration with customer lookup",
            "recommendations": "Menu recommendations based on preferences",
            "payment_processing": "Credit card processing for delivery orders via USAePay gateway",
            "sms_messaging": "Send text messages to customers via Twilio",
            "order_management": "Complete order placement with payment processing and storage"
        },
        "docs": "/docs",
        "redoc": "/redoc",
        "available_endpoints": {
            "business_hours": "POST /is_in_business_hour?restaurant_id={1|2}&phone_number=optional",
            "lunch_hours": "POST /is_in_lunch_hour?restaurant_id={1|2}", 
            "order_total": "POST /get-order-total?restaurant_id={1|2}",
            "recommendations": "POST /recommend?restaurant_id={1|2}",
            "store_hours": "GET|PUT /store-hours/{1|2}",
            "customer_management": {
                "update_name": "POST /update_customer_name?phone_number=xxx&customer_name=xxx"
            },
            "payment_processing": {
                "charge_credit_card": "POST /charge-credit-card"
            },
            "sms_messaging": {
                "send_text_message": "POST /send-text-message"
            },
            "order_management": {
                "place_order": "POST /place-order?restaurant_id={1|2}"
            },
            "database": {
                "test_connection": "GET /test-db",
                "health": "GET /health"
            }
        },
        "supported_restaurant_ids": [1, 2],
        "new_features": {
            "customer_memory": "Agents can now remember customer names across calls",
            "enhanced_business_hours": "Returns all dynamic variables needed by Retell AI",
            "phone_lookup": "Customer lookup by phone number in business hours check",
            "postgresql_support": "Production-ready PostgreSQL database integration"
        },
        "examples": {
            "restaurant_1": {
                "business_hours": "POST /is_in_business_hour?restaurant_id=1",
                "business_hours_with_customer": "POST /is_in_business_hour?restaurant_id=1&phone_number=2025551234",
                "recommendations": "POST /recommend?restaurant_id=1"
            },
            "restaurant_2": {
                "business_hours": "POST /is_in_business_hour?restaurant_id=2", 
                "business_hours_with_customer": "POST /is_in_business_hour?restaurant_id=2&phone_number=2025551234",
                "recommendations": "POST /recommend?restaurant_id=2"
            }
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring"""
    try:
        db_status = test_database_connection()
        return {
            "status": "healthy", 
            "service": "keyra-restaurant-api", 
            "version": "2.0.0",
            "database": db_status
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "keyra-restaurant-api", 
            "version": "2.0.0",
            "database": {"status": "error", "error": str(e)}
        }

@app.get("/test-db")
async def test_database():
    """Test database connection and return detailed information"""
    try:
        db_info = test_database_connection()
        return {
            "message": "Database connection test completed",
            "connection_info": db_info,
            "timestamp": "2025-01-15T12:00:00Z"
        }
    except Exception as e:
        logger.error(f"Database test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database test failed: {str(e)}")

@app.post("/setup-database")
async def setup_database(db = Depends(get_db)):
    """One-time setup endpoint to initialize database tables and restaurant tax rates"""
    try:
        from database_models import Base, Restaurant, engine
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        # Check if restaurants already exist
        existing = db.query(Restaurant).all()
        if existing:
            return {
                "message": "Database already set up",
                "restaurants": [{"id": r.id, "name": r.name, "tax_rate": r.tax_rate} for r in existing]
            }
        
        # Create restaurant records with tax rates
        restaurant_1 = Restaurant(
            id=1,
            name="Umai Nori Restaurant 1",
            address="123 Main St, City, State 12345",
            phone="(555) 123-4567",
            business_hours={"monday": "11:00-22:00", "tuesday": "11:00-22:00", "wednesday": "11:00-22:00", "thursday": "11:00-22:00", "friday": "11:00-22:00", "saturday": "11:00-22:00", "sunday": "11:00-22:00"},
            tax_rate=0.06  # 6% tax rate
        )
        
        restaurant_2 = Restaurant(
            id=2, 
            name="Umai Nori Restaurant 2",
            address="456 Oak Ave, City, State 12345",
            phone="(555) 987-6543",
            business_hours={"monday": "11:00-22:00", "tuesday": "11:00-22:00", "wednesday": "11:00-22:00", "thursday": "11:00-22:00", "friday": "11:00-22:00", "saturday": "11:00-22:00", "sunday": "11:00-22:00"},
            tax_rate=0.10  # 10% tax rate
        )
        
        db.add(restaurant_1)
        db.add(restaurant_2)
        db.commit()
        
        return {
            "message": "Database and restaurant tax rates set up successfully",
            "restaurants": [
                {"id": "1", "name": "Umai Nori Restaurant 1", "tax_rate": 0.06},
                {"id": "2", "name": "Umai Nori Restaurant 2", "tax_rate": 0.10}
            ]
        }
        
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to set up database: {str(e)}")

@app.get("/debug")
async def debug_info():
    """Debug endpoint to check what routes are available"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods)
            })
    
    return {
        "total_routes": len(app.routes),
        "routes": routes,
        "business_endpoints": {
            "is_in_business_hour": {
                "path": "/is_in_business_hour",
                "method": "POST", 
                "usage": "POST /is_in_business_hour?restaurant_id=1&phone_number=optional",
                "exists": any(r.path == "/is_in_business_hour" for r in app.routes if hasattr(r, 'path')),
                "enhanced": "Now supports customer lookup and returns dynamic variables"
            },
            "is_in_lunch_hour": {
                "path": "/is_in_lunch_hour",
                "method": "POST",
                "usage": "POST /is_in_lunch_hour?restaurant_id=2", 
                "exists": any(r.path == "/is_in_lunch_hour" for r in app.routes if hasattr(r, 'path'))
            },
            "recommend": {
                "path": "/recommend",
                "method": "POST",
                "usage": "POST /recommend?restaurant_id=1",
                "exists": any(r.path == "/recommend" for r in app.routes if hasattr(r, 'path'))
            },
            "update_customer_name": {
                "path": "/update_customer_name",
                "method": "POST",
                "usage": "POST /update_customer_name?phone_number=xxx&customer_name=xxx",
                "exists": any(r.path == "/update_customer_name" for r in app.routes if hasattr(r, 'path')),
                "new": "Allows updating customer names during conversations"
            },
            "test_database": {
                "path": "/test-db",
                "method": "GET",
                "usage": "GET /test-db",
                "exists": any(r.path == "/test-db" for r in app.routes if hasattr(r, 'path')),
                "new": "Test PostgreSQL database connection"
            }
        },
        "note": "restaurant_id is passed as a query parameter, not in the URL path"
    }

# Enhanced Business Operations Endpoints
@app.post("/is_in_business_hour", response_model=DynamicVariablesResponse)
async def enhanced_business_hour_check(
    restaurant_id: str = Query(..., description="Restaurant ID"),
    phone_number: Optional[str] = Query(None, description="Customer phone number for lookup"),
    db = Depends(get_db)
):
    """
    Enhanced business hours check with customer lookup.
    Returns all dynamic variables needed by Retell AI agent including:
    - Business hours status
    - Lunch hours status  
    - Customer name (if found)
    - Pickup time
    - Current time
    - Greeting context (new/returning customer)
    """
    try:
        # Get current time in Eastern timezone
        current_time = get_current_time_eastern()
        current_day = get_day_name(current_time.weekday())
        
        # Load business hours
        store_hours = load_store_hours(restaurant_id)
        
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
        if current_day not in store_hours.business_hours:
            is_open = False
            business_message = "No business hours configured for this day"
        else:
            day_hours = store_hours.business_hours[current_day]
            if day_hours.is_closed:
                is_open = False
                business_message = "Restaurant is closed today"
            else:
                is_open = is_time_in_business_hours(current_time.time(), day_hours)
                if day_hours.periods:
                    hours_display = ", ".join([f"{p.open_time} - {p.close_time}" for p in day_hours.periods])
                else:
                    hours_display = f"{day_hours.open_time} - {day_hours.close_time}"
                
                business_message = f"Today's hours: {hours_display}"
        
        # Check lunch hours
        is_lunch = False
        lunch_message = "Lunch service not available"
        if store_hours.lunch_hours and current_day in store_hours.lunch_hours:
            lunch_hours_today = store_hours.lunch_hours[current_day]
            if not lunch_hours_today.is_closed:
                is_lunch = is_time_in_business_hours(current_time.time(), lunch_hours_today)
                if lunch_hours_today.periods:
                    lunch_display = ", ".join([f"{p.open_time} - {p.close_time}" for p in lunch_hours_today.periods])
                else:
                    lunch_display = f"{lunch_hours_today.open_time} - {lunch_hours_today.close_time}"
                lunch_message = f"Lunch hours: {lunch_display}"
        
        # Calculate pickup time
        pickup_time = calculate_pickup_time(preferred_pickup)
        
        return DynamicVariablesResponse(
            is_in_business_hour=is_open,
            is_lunch_hour=is_lunch,
            current_eastern_time=format_time_for_voice(current_time),
            pickup_time=pickup_time,
            customer_name=customer_name,
            customer_phone_number=customer_phone,
            greeting_context=greeting_context,
            business_hours_message=business_message,
            lunch_hours_message=lunch_message
        )
        
    except Exception as e:
        logger.error(f"Error checking business hours: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check business hours")

@app.post("/update_customer_name")
async def update_customer_name_endpoint(
    phone_number: str = Query(..., description="Customer phone number"),
    customer_name: str = Query(..., description="Customer name"),
    db = Depends(get_db)
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

@app.post("/is_in_lunch_hour")
async def is_in_lunch_hour(restaurant_id: str = Query(..., description="Restaurant ID")):
    """Check if restaurant is currently in lunch hours"""
    try:
        return await _check_lunch_hours(restaurant_id)
    except Exception as e:
        logger.error(f"Error checking lunch hours: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check lunch hours")

@app.post("/get-order-total", response_model=OrderTotalResponse)
async def get_order_total(
    request: Request,
    restaurant_id: str = Query(..., description="Restaurant ID")
):
    """Calculate order total including tax"""
    try:
        # First, let's capture the raw request body for debugging
        body = await request.body()
        raw_body = body.decode('utf-8') if body else ''
        logger.info(f"RAW REQUEST BODY: {raw_body}")
        
        # Parse the JSON manually for debugging
        import json
        try:
            json_data = json.loads(raw_body) if raw_body else {}
            logger.info(f"PARSED JSON DATA: {json_data}")
        except json.JSONDecodeError as je:
            logger.error(f"JSON DECODE ERROR: {str(je)}")
            logger.error(f"RAW BODY CAUSING ERROR: {repr(raw_body)}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(je)}")
        
        # Extract order data - handle both direct format and Retell wrapper format
        if 'args' in json_data and isinstance(json_data['args'], dict):
            # Retell format: {"call": {...}, "name": "...", "args": {actual_order_data}}
            order_data = json_data['args']
            logger.info(f"EXTRACTED ORDER DATA FROM RETELL WRAPPER: {order_data}")
        else:
            # Direct format: {order_data}
            order_data = json_data
            logger.info(f"USING DIRECT ORDER DATA: {order_data}")
        
        # Now try to validate with Pydantic
        try:
            order = OrderRequest(**order_data)
            logger.info(f"PYDANTIC VALIDATION SUCCESS: {order}")
        except Exception as validation_error:
            logger.error(f"PYDANTIC VALIDATION ERROR: {str(validation_error)}")
            logger.error(f"ORDER DATA THAT FAILED VALIDATION: {order_data}")
            raise HTTPException(status_code=422, detail=f"Validation error: {str(validation_error)}")
        
        logger.info(f"Processing order total for restaurant {restaurant_id}")
        
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
        
        # Calculate tax using restaurant-specific rate
        tax_rate = get_restaurant_tax_rate(restaurant_id)
        logger.info(f"Tax rate for restaurant {restaurant_id}: {tax_rate}")
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        response = OrderTotalResponse(
            subtotal=round(subtotal, 2),
            tax_amount=round(tax_amount, 2),
            total=round(total, 2),
            item_breakdown=item_breakdown
        )
        
        logger.info(f"FINAL RESPONSE: {response}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate order total: {str(e)}")

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

# Recommendation endpoint (existing functionality)
@app.post("/recommend")
async def recommend(request: Request, restaurant_id: str = Query(..., description="Restaurant ID")):
    """Get menu recommendations based on preferences"""
    try:
        # Import here to avoid circular imports and handle missing dependencies gracefully
        import os
        if not os.getenv("GEMINI_API_KEY"):
            logger.warning("GEMINI_API_KEY not found, recommendation service unavailable")
            return {
                "error": "Recommendation service temporarily unavailable",
                "message": "GEMINI_API_KEY not configured",
                "available_services": ["business_hours", "lunch_hours", "order_total", "store_hours"]
            }
        
        from recommend import get_recommendation
        
        # Parse request body
        body = await request.json()
        
        # Get recommendation using the restaurant_id
        recommendation = await get_recommendation(body, restaurant_id)
        return recommendation
        
    except ImportError as e:
        logger.error(f"Import error in recommendation service: {str(e)}")
        return {
            "error": "Recommendation service unavailable", 
            "message": "Missing dependencies for recommendation engine",
            "available_services": ["business_hours", "lunch_hours", "order_total", "store_hours"]
        }
    except Exception as e:
        logger.error(f"Error getting recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get recommendation")

# USAePay Credit Card Processing Endpoint
@app.post("/charge-credit-card", response_model=CreditCardResponse)
async def charge_credit_card(card_request: CreditCardRequest):
    """
    Charge a credit card for delivery orders using USAePay gateway.
    
    This endpoint processes credit card payments by:
    1. Taking the base charge amount and tip amount
    2. Processing the card through USAePay
    3. Returning transaction details including success/failure status
    
    Required environment variables:
    - USAEPAY_API_KEY: Your USAePay API/Source Key
    - USAEPAY_API_PIN: Your USAePay API PIN (optional but recommended)
    - USAEPAY_ENVIRONMENT: 'sandbox' or 'production' (defaults to 'sandbox')
    """
    try:
        # Get USAePay configuration from environment variables
        api_key = os.getenv("USAEPAY_API_KEY")
        api_pin = os.getenv("USAEPAY_API_PIN", "")
        environment = os.getenv("USAEPAY_ENVIRONMENT", "sandbox")
        
        if not api_key:
            logger.error("USAEPAY_API_KEY environment variable not set")
            raise HTTPException(
                status_code=500, 
                detail="Payment processing not configured. Missing API key."
            )
        
        # Calculate total amount (base charge + tip)
        total_amount = round(card_request.base_charge_amount + card_request.tip_amount, 2)
        
        # Set up USAePay authentication
        if environment.lower() == "production":
            usaepay.api.set_authentication(api_key, api_pin)
            gateway_host = "www.usaepay.com"
        else:
            usaepay.api.set_authentication(api_key, api_pin)
            gateway_host = "sandbox.usaepay.com"
        
        # Prepare transaction data
        transaction_data = {
            "command": "cc:sale",
            "amount": str(total_amount),
            "creditcard": {
                "number": card_request.credit_card_number,
                "expiration": card_request.credit_card_expiration_date,
                "cvc": card_request.credit_card_cvv,
                "cardholder": card_request.cardholder_name,
                "avs_street": card_request.billing_street,
                "avs_zip": card_request.credit_card_zip_code
            },
            "amount_detail": {
                "subtotal": str(card_request.base_charge_amount),
                "tip": str(card_request.tip_amount)
            },
            "description": "Delivery Order Payment",
            "invoice": f"ORDER_{hash(str(card_request.credit_card_number))}_{total_amount}"[:10]
        }
        
        logger.info(f"Processing credit card charge for ${total_amount}")
        
        # Process the transaction through USAePay
        try:
            # Create transaction using USAePay SDK
            transaction = usaepay.transactions.Transaction.create(transaction_data)
            
            # Check if transaction was successful
            if transaction.result_code == "A":  # Approved
                logger.info(f"Credit card charge successful. Transaction ID: {transaction.key}")
                return CreditCardResponse(
                    success=True,
                    transaction_id=transaction.key,
                    auth_code=transaction.authcode,
                    result=transaction.result,
                    result_code=transaction.result_code,
                    total_amount=total_amount,
                    avs_result=getattr(transaction.avs, 'result', None) if hasattr(transaction, 'avs') else None,
                    cvv_result=getattr(transaction.cvc, 'result', None) if hasattr(transaction, 'cvc') else None
                )
            else:
                # Transaction declined or failed
                logger.warning(f"Credit card charge declined. Result: {transaction.result}")
                return CreditCardResponse(
                    success=False,
                    result=transaction.result,
                    result_code=transaction.result_code,
                    total_amount=total_amount,
                    error_message=transaction.result
                )
                
        except Exception as transaction_error:
            logger.error(f"USAePay transaction error: {str(transaction_error)}")
            return CreditCardResponse(
                success=False,
                result="Transaction Error",
                result_code="E",
                total_amount=total_amount,
                error_message=f"Payment processing failed: {str(transaction_error)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in credit card processing: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error during payment processing: {str(e)}"
        )

# Twilio SMS Endpoint
@app.post("/send-text-message", response_model=SMSResponse)
async def send_text_message(request: Request):
    """
    Send an SMS message to a customer using Twilio.
    
    This endpoint sends text messages by:
    1. Taking the customer phone number and message content
    2. Processing the request through Twilio's SMS API
    3. Returning message status and details
    
    Required environment variables:
    - TWILIO_ACCOUNT_SID: Your Twilio Account SID
    - TWILIO_AUTH_TOKEN: Your Twilio Auth Token
    - TWILIO_PHONE_NUMBER: Your Twilio phone number (from number)
    """
    try:
        # Get raw request body and parse
        body = await request.body()
        raw_body = body.decode('utf-8') if body else ''
        logger.info(f"SMS REQUEST BODY: {raw_body}")
        
        import json
        try:
            json_data = json.loads(raw_body) if raw_body else {}
            logger.info(f"SMS PARSED JSON: {json_data}")
        except json.JSONDecodeError as je:
            logger.error(f"SMS JSON DECODE ERROR: {str(je)}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(je)}")
        
        # Extract SMS data - handle both direct format and Retell wrapper format
        if 'args' in json_data and isinstance(json_data['args'], dict):
            # Retell format: {"call": {...}, "name": "...", "args": {actual_sms_data}}
            sms_data = json_data['args']
            logger.info(f"EXTRACTED SMS DATA FROM RETELL WRAPPER: {sms_data}")
        else:
            # Direct format: {sms_data}
            sms_data = json_data
            logger.info(f"USING DIRECT SMS DATA: {sms_data}")
        
        # Validate SMS request data
        try:
            sms_request = SMSRequest(**sms_data)
            logger.info(f"SMS VALIDATION SUCCESS: {sms_request}")
        except Exception as validation_error:
            logger.error(f"SMS VALIDATION ERROR: {str(validation_error)}")
            logger.error(f"SMS DATA THAT FAILED VALIDATION: {sms_data}")
            raise HTTPException(status_code=422, detail=f"Validation error: {str(validation_error)}")
        
        # Get Twilio configuration from environment variables
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
        
        if not account_sid or not auth_token or not twilio_phone:
            missing_vars = []
            if not account_sid: missing_vars.append("TWILIO_ACCOUNT_SID")
            if not auth_token: missing_vars.append("TWILIO_AUTH_TOKEN")
            if not twilio_phone: missing_vars.append("TWILIO_PHONE_NUMBER")
            
            logger.error(f"Missing Twilio environment variables: {missing_vars}")
            raise HTTPException(
                status_code=500, 
                detail=f"SMS service not configured. Missing environment variables: {', '.join(missing_vars)}"
            )
        
        # Initialize Twilio client
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            logger.info(f"Twilio client initialized successfully")
        except ImportError:
            logger.error("Twilio library not installed")
            raise HTTPException(
                status_code=500, 
                detail="SMS service unavailable. Twilio library not installed."
            )
        except Exception as client_error:
            logger.error(f"Failed to initialize Twilio client: {str(client_error)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to initialize SMS service: {str(client_error)}"
            )
        
        # Send SMS message
        try:
            logger.info(f"Sending SMS to {sms_request.customer_phone} from {twilio_phone}")
            logger.info(f"Message content: {sms_request.message}")
            
            message = client.messages.create(
                body=sms_request.message,
                from_=twilio_phone,
                to=sms_request.customer_phone
            )
            
            logger.info(f"SMS sent successfully. Message SID: {message.sid}")
            
            return SMSResponse(
                success=True,
                message_sid=message.sid,
                status=message.status,
                phone_number=sms_request.customer_phone
            )
            
        except Exception as sms_error:
            logger.error(f"Failed to send SMS: {str(sms_error)}")
            return SMSResponse(
                success=False,
                status="failed",
                error_message=f"Failed to send SMS: {str(sms_error)}",
                phone_number=sms_request.customer_phone
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in SMS service: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error in SMS service: {str(e)}"
        )

# Place Order Endpoint
@app.post("/place-order", response_model=PlaceOrderResponse)
async def place_order(
    request: Request,
    restaurant_id: str = Query(..., description="Restaurant ID"),
    db: Session = Depends(get_db)
):
    """
    Place a complete order including payment processing and storage.
    
    This endpoint handles the full order process by:
    1. Validating the order data
    2. Calculating order totals with restaurant-specific tax rates
    3. Processing payment (if credit card payment)
    4. Storing the order in the database
    5. Creating or updating customer information
    6. Returning order confirmation details
    
    Supports both cash and credit card payments.
    For credit card payments, requires USAePay environment variables.
    """
    try:
        # Get raw request body and parse
        body = await request.body()
        raw_body = body.decode('utf-8') if body else ''
        logger.info(f"PLACE ORDER REQUEST BODY: {raw_body}")
        
        import json
        try:
            json_data = json.loads(raw_body) if raw_body else {}
            logger.info(f"PLACE ORDER PARSED JSON: {json_data}")
        except json.JSONDecodeError as je:
            logger.error(f"PLACE ORDER JSON DECODE ERROR: {str(je)}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(je)}")
        
        # Extract order data - handle both direct format and Retell wrapper format
        if 'args' in json_data and isinstance(json_data['args'], dict):
            # Retell format: {"call": {...}, "name": "...", "args": {actual_order_data}}
            order_data = json_data['args']
            logger.info(f"EXTRACTED ORDER DATA FROM RETELL WRAPPER: {order_data}")
        else:
            # Direct format: {order_data}
            order_data = json_data
            logger.info(f"USING DIRECT ORDER DATA: {order_data}")
        
        # Validate order request data
        try:
            order_request = PlaceOrderRequest(**order_data)
            logger.info(f"ORDER VALIDATION SUCCESS: {order_request.customer_name}")
        except Exception as validation_error:
            logger.error(f"ORDER VALIDATION ERROR: {str(validation_error)}")
            logger.error(f"ORDER DATA THAT FAILED VALIDATION: {order_data}")
            raise HTTPException(status_code=422, detail=f"Validation error: {str(validation_error)}")
        
        # Calculate order total using existing business logic
        subtotal = 0
        item_breakdown = []
        
        for item in order_request.order_items:
            # Convert to the existing OrderItem format for calculation
            from business_operations import OrderItem, Modifier
            
            # Convert modifiers
            order_modifiers = []
            if item.modifiers:
                for mod in item.modifiers:
                    order_modifiers.append(Modifier(
                        modifier_name=mod.modifier_name,
                        modifier_quantity=mod.modifier_quantity,
                        modifier_price=mod.modifier_price
                    ))
            
            # Create OrderItem for calculation
            calc_item = OrderItem(
                item_name=item.item_name,
                item_quantity=item.item_quantity,
                item_base_price=item.item_base_price,
                modifiers=order_modifiers,
                special_instructions=item.special_instructions or ""
            )
            
            item_total = calculate_item_total(calc_item)
            subtotal += item_total
            
            # Create breakdown for this item
            breakdown_item = {
                "item_name": item.item_name,
                "item_quantity": item.item_quantity,
                "item_base_price": item.item_base_price,
                "item_subtotal": item.item_base_price * item.item_quantity,
                "modifier_total": 0,
                "item_total": item_total,
                "special_instructions": item.special_instructions or ""
            }
            
            # Add modifier details
            if item.modifiers:
                modifier_total = 0
                modifiers_detail = []
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
        
        # Calculate tax using restaurant-specific rate
        tax_rate = get_restaurant_tax_rate(restaurant_id)
        logger.info(f"Tax rate for restaurant {restaurant_id}: {tax_rate}")
        tax_amount = subtotal * tax_rate
        total_amount = subtotal + tax_amount + order_request.delivery_fee + order_request.tip_amount
        
        logger.info(f"Order totals: subtotal=${subtotal:.2f}, tax=${tax_amount:.2f}, delivery=${order_request.delivery_fee:.2f}, tip=${order_request.tip_amount:.2f}, total=${total_amount:.2f}")
        
        # Process payment if credit card
        transaction_id = None
        payment_status = "pending"
        
        if order_request.payment_type and order_request.payment_type.lower() in ["credit_card", "card", "credit"]:
            if not order_request.credit_card_number or not order_request.credit_card_expiration_date or not order_request.credit_card_security_code:
                raise HTTPException(status_code=400, detail="Credit card information required for card payments")
            
            # Process credit card payment using existing logic
            try:
                # Create CreditCardRequest for payment processing
                card_request = CreditCardRequest(
                    base_charge_amount=subtotal + tax_amount + order_request.delivery_fee,
                    credit_card_number=order_request.credit_card_number,
                    credit_card_cvv=order_request.credit_card_security_code,
                    credit_card_zip_code=order_request.credit_card_zip_code or "",
                    credit_card_expiration_date=order_request.credit_card_expiration_date,
                    cardholder_name=order_request.customer_name,
                    tip_amount=order_request.tip_amount,
                    billing_street=order_request.customer_address or ""
                )
                
                # Process payment (reuse existing credit card logic)
                payment_result = await process_credit_card_payment(card_request)
                
                if payment_result.success:
                    payment_status = "paid"
                    transaction_id = payment_result.transaction_id
                    logger.info(f"Payment successful: {transaction_id}")
                else:
                    payment_status = "failed"
                    logger.error(f"Payment failed: {payment_result.error_message}")
                    return PlaceOrderResponse(
                        success=False,
                        total_amount=total_amount,
                        payment_status=payment_status,
                        message="Order could not be placed due to payment failure",
                        error_message=payment_result.error_message
                    )
                    
            except Exception as payment_error:
                logger.error(f"Payment processing error: {str(payment_error)}")
                return PlaceOrderResponse(
                    success=False,
                    total_amount=total_amount,
                    payment_status="failed",
                    message="Order could not be placed due to payment processing error",
                    error_message=str(payment_error)
                )
        else:
            # Cash payment
            payment_status = "cash"
            logger.info("Cash payment selected")
        
        # Create or update customer
        customer = lookup_or_create_customer(db, order_request.customer_phone, order_request.customer_name)
        
        # Store order in database
        from database_models import Order
        
        # Prepare complete order data for storage
        order_data_for_db = {
            "restaurant_id": int(restaurant_id),
            "customer_info": {
                "name": order_request.customer_name,
                "phone": order_request.customer_phone,
                "address": order_request.customer_address or ""
            },
            "order_details": {
                "order_type": order_request.order_type,
                "pick_up_time": order_request.pick_up_time or "",
                "order_notes": order_request.order_notes,
                "items": [
                    {
                        "item_name": item.item_name,
                        "item_quantity": item.item_quantity,
                        "item_base_price": item.item_base_price,
                        "special_instructions": item.special_instructions or "",
                        "modifiers": [
                            {
                                "modifier_name": mod.modifier_name,
                                "modifier_quantity": mod.modifier_quantity,
                                "modifier_price": mod.modifier_price
                            } for mod in item.modifiers
                        ]
                    } for item in order_request.order_items
                ]
            },
            "pricing": {
                "subtotal": round(subtotal, 2),
                "tax_amount": round(tax_amount, 2),
                "tax_rate": tax_rate,
                "delivery_fee": order_request.delivery_fee,
                "tip_amount": order_request.tip_amount,
                "total_amount": round(total_amount, 2)
            },
            "payment": {
                "payment_type": order_request.payment_type or "cash",
                "payment_status": payment_status,
                "transaction_id": transaction_id
            },
            "item_breakdown": item_breakdown
        }
        
        # Create order record
        new_order = Order(
            customer_id=customer.id,
            restaurant_id=int(restaurant_id),
            order_data=order_data_for_db,
            total_amount=total_amount
        )
        
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        
        # Generate order number
        order_number = f"ORD-{restaurant_id}-{new_order.id:06d}"
        
        # Calculate estimated pickup time
        estimated_pickup_time = order_request.pick_up_time or "ASAP"
        if not order_request.pick_up_time or order_request.pick_up_time.lower() in ["asap", ""]:
            # Default to 20-30 minutes from now
            from datetime import datetime, timedelta
            import pytz
            eastern = pytz.timezone('America/New_York')
            pickup_time = datetime.now(eastern) + timedelta(minutes=25)
            estimated_pickup_time = pickup_time.strftime("%I:%M %p")
        
        logger.info(f"Order placed successfully: {order_number} for ${total_amount:.2f}")
        
        return PlaceOrderResponse(
            success=True,
            order_id=str(new_order.id),
            order_number=order_number,
            total_amount=round(total_amount, 2),
            payment_status=payment_status,
            estimated_pickup_time=estimated_pickup_time,
            message=f"Order {order_number} placed successfully! {f'Estimated pickup time: {estimated_pickup_time}' if order_request.order_type.lower() in ['pickup', 'pick_up', 'pick-up'] else ''}",
            transaction_id=transaction_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in place order: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error placing order: {str(e)}"
        )

# Helper function for credit card processing (extracted from existing endpoint)
async def process_credit_card_payment(card_request: CreditCardRequest) -> CreditCardResponse:
    """Process credit card payment using USAePay"""
    try:
        # Get USAePay configuration from environment variables
        api_key = os.getenv("USAEPAY_API_KEY")
        api_pin = os.getenv("USAEPAY_API_PIN", "")
        environment = os.getenv("USAEPAY_ENVIRONMENT", "sandbox")
        
        if not api_key:
            logger.error("USAEPAY_API_KEY environment variable not set")
            return CreditCardResponse(
                success=False,
                result="Configuration Error",
                result_code="E",
                total_amount=card_request.base_charge_amount + card_request.tip_amount,
                error_message="Payment processing not configured. Missing API key."
            )
        
        # Calculate total amount (base charge + tip)
        total_amount = round(card_request.base_charge_amount + card_request.tip_amount, 2)
        
        # Set up USAePay authentication
        if environment.lower() == "production":
            usaepay.api.set_authentication(api_key, api_pin)
            gateway_host = "www.usaepay.com"
        else:
            usaepay.api.set_authentication(api_key, api_pin)
            gateway_host = "sandbox.usaepay.com"
        
        # Prepare transaction data
        transaction_data = {
            "command": "cc:sale",
            "amount": str(total_amount),
            "creditcard": {
                "number": card_request.credit_card_number,
                "expiration": card_request.credit_card_expiration_date,
                "cvc": card_request.credit_card_cvv,
                "cardholder": card_request.cardholder_name,
                "avs_street": card_request.billing_street,
                "avs_zip": card_request.credit_card_zip_code
            },
            "amount_detail": {
                "subtotal": str(card_request.base_charge_amount),
                "tip": str(card_request.tip_amount)
            },
            "description": "Restaurant Order Payment",
            "invoice": f"ORDER_{hash(str(card_request.credit_card_number))}_{total_amount}"[:10]
        }
        
        logger.info(f"Processing credit card charge for ${total_amount}")
        
        # Process the transaction through USAePay
        try:
            # Create transaction using USAePay SDK
            transaction = usaepay.transactions.Transaction.create(transaction_data)
            
            # Check if transaction was successful
            if transaction.result_code == "A":  # Approved
                logger.info(f"Credit card charge successful. Transaction ID: {transaction.key}")
                return CreditCardResponse(
                    success=True,
                    transaction_id=transaction.key,
                    auth_code=transaction.authcode,
                    result=transaction.result,
                    result_code=transaction.result_code,
                    total_amount=total_amount,
                    avs_result=getattr(transaction.avs, 'result', None) if hasattr(transaction, 'avs') else None,
                    cvv_result=getattr(transaction.cvc, 'result', None) if hasattr(transaction, 'cvc') else None
                )
            else:
                # Transaction declined or failed
                logger.warning(f"Credit card charge declined. Result: {transaction.result}")
                return CreditCardResponse(
                    success=False,
                    result=transaction.result,
                    result_code=transaction.result_code,
                    total_amount=total_amount,
                    error_message=transaction.result
                )
                
        except Exception as transaction_error:
            logger.error(f"USAePay transaction error: {str(transaction_error)}")
            return CreditCardResponse(
                success=False,
                result="Transaction Error",
                result_code="E",
                total_amount=total_amount,
                error_message=f"Payment processing failed: {str(transaction_error)}"
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in credit card processing: {str(e)}")
        return CreditCardResponse(
            success=False,
            result="System Error",
            result_code="E",
            total_amount=card_request.base_charge_amount + card_request.tip_amount,
            error_message=f"Unexpected error during payment processing: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 