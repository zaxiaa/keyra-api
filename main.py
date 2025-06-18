#!/usr/bin/env python3
"""
Main FastAPI application that combines business operations and recommendation services
"""

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the internal functions directly from business_operations
from business_operations import _check_business_hours, _check_lunch_hours, load_store_hours, save_store_hours, calculate_item_total
from business_operations import OrderRequest, OrderTotalResponse, StoreHours, TAX_RATE

# Create main FastAPI app
app = FastAPI(
    title="Keyra Restaurant API",
    description="Combined API for restaurant business operations and recommendations",
    version="1.0.0",
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
        "message": "Keyra Restaurant API",
        "services": {
            "business_operations": "Business hours, lunch hours, order totals, store configuration",
            "recommendations": "Menu recommendations based on preferences"
        },
        "docs": "/docs",
        "redoc": "/redoc",
        "available_endpoints": {
            "business_hours": "POST /is_in_business_hour?restaurant_id=1",
            "lunch_hours": "POST /is_in_lunch_hour?restaurant_id=1", 
            "order_total": "POST /get-order-total",
            "recommendations": "POST /recommend",
            "store_hours": "GET /store-hours/1"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring"""
    return {"status": "healthy", "service": "keyra-restaurant-api"}

# Business Operations Endpoints
@app.post("/is_in_business_hour")
async def is_in_business_hour(restaurant_id: str = Query(..., description="Restaurant ID")):
    """Check if restaurant is currently in business hours"""
    try:
        return await _check_business_hours(restaurant_id)
    except Exception as e:
        logger.error(f"Error checking business hours: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check business hours")

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

# Recommendation Endpoint
@app.post("/recommend")
async def recommend(request: Request):
    """Get menu recommendations"""
    from recommend import recommend as recommend_func
    return await recommend_func(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 