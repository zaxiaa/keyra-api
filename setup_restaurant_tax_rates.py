#!/usr/bin/env python3
"""
Script to set up restaurant tax rates in the database
"""

from database_models import Restaurant, create_tables, SessionLocal, test_database_connection
from sqlalchemy import text

def setup_restaurant_tax_rates():
    """Set up restaurant tax rates in the database"""
    
    # Test database connection first
    db_info = test_database_connection()
    print("Database connection:", db_info)
    
    if db_info["status"] != "connected":
        print("❌ Database connection failed!")
        return False
    
    # Create tables if they don't exist
    create_tables()
    
    db = SessionLocal()
    try:
        # Check if restaurants table exists and has tax_rate column
        try:
            result = db.execute(text("SELECT tax_rate FROM restaurants LIMIT 1"))
            print("✅ tax_rate column already exists")
        except Exception as e:
            print(f"Adding tax_rate column to restaurants table...")
            try:
                # Add tax_rate column if it doesn't exist
                db.execute(text("ALTER TABLE restaurants ADD COLUMN tax_rate FLOAT DEFAULT 0.06"))
                db.commit()
                print("✅ Added tax_rate column")
            except Exception as e2:
                print(f"Error adding tax_rate column: {e2}")
                return False
        
        # Create or update restaurant records
        restaurants_data = [
            {"id": 1, "name": "Umai Nori Restaurant 1", "tax_rate": 0.06},
            {"id": 2, "name": "Umai Nori Restaurant 2", "tax_rate": 0.10}
        ]
        
        for restaurant_data in restaurants_data:
            # Check if restaurant exists
            existing = db.query(Restaurant).filter(Restaurant.id == restaurant_data["id"]).first()
            
            if existing:
                # Update existing restaurant
                existing.tax_rate = restaurant_data["tax_rate"]
                existing.name = restaurant_data["name"]
                print(f"✅ Updated restaurant {restaurant_data['id']} with {restaurant_data['tax_rate']*100}% tax rate")
            else:
                # Create new restaurant with minimal required fields
                new_restaurant = Restaurant(
                    id=restaurant_data["id"],
                    name=restaurant_data["name"],
                    address="Default Address",
                    phone="555-0000",
                    business_hours={"monday": {"periods": [{"open_time": "11:00", "close_time": "22:00"}], "is_closed": False}},
                    tax_rate=restaurant_data["tax_rate"]
                )
                db.add(new_restaurant)
                print(f"✅ Created restaurant {restaurant_data['id']} with {restaurant_data['tax_rate']*100}% tax rate")
        
        db.commit()
        print("\n🎉 Restaurant tax rates setup complete!")
        
        # Verify the setup
        print("\nVerification:")
        restaurants = db.query(Restaurant).all()
        for restaurant in restaurants:
            print(f"  Restaurant {restaurant.id}: {restaurant.name} - {restaurant.tax_rate*100}% tax rate")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up restaurant tax rates: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    setup_restaurant_tax_rates() 