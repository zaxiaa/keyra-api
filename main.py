#!/usr/bin/env python3
"""
Main FastAPI application that combines business operations and recommendation services
"""

from fastapi import FastAPI, Query, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the internal functions directly from business_operations
from business_operations import _check_lunch_hours, load_store_hours, save_store_hours, calculate_item_total
from business_operations import OrderRequest, OrderTotalResponse, StoreHours, TAX_RATE, DynamicVariablesResponse
from business_operations import get_db, lookup_or_create_customer, is_in_business_hour_post, update_customer_name

# Import database test function
from database_models import test_database_connection

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
            "recommendations": "Menu recommendations based on preferences"
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
        return await is_in_business_hour_post(restaurant_id, phone_number, db)
    except Exception as e:
        logger.error(f"Error in enhanced business hours check: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check business hours")

@app.post("/update_customer_name")
async def update_customer_name_endpoint(
    phone_number: str = Query(..., description="Customer phone number"),
    customer_name: str = Query(..., description="Customer name"),
    db = Depends(get_db)
):
    """Update customer name when collected during conversation"""
    try:
        return await update_customer_name(phone_number, customer_name, db)
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
    order: OrderRequest,
    restaurant_id: str = Query(..., description="Restaurant ID")
):
    """Calculate order total including tax"""
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 