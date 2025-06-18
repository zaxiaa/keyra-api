#!/usr/bin/env python3
"""
Main FastAPI application that combines business operations and recommendation services
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import the individual apps
from business_operations import app as business_app
from recommend import app as recommend_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Add a main root endpoint
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
            "business_hours": "/is_in_business_hour?restaurant_id=1",
            "lunch_hours": "/is_in_lunch_hour?restaurant_id=1", 
            "order_total": "/get-order-total",
            "recommendations": "/recommend",
            "store_hours": "/store-hours/1"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring"""
    return {"status": "healthy", "service": "keyra-restaurant-api"}

# Include business operations routes (excluding root and health to avoid conflicts)
for route in business_app.routes:
    if hasattr(route, 'path') and route.path not in ['/', '/health']:
        app.routes.append(route)

# Include recommendation routes (excluding root and health to avoid conflicts)  
for route in recommend_app.routes:
    if hasattr(route, 'path') and route.path not in ['/', '/health']:
        app.routes.append(route)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 