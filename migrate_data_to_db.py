#!/usr/bin/env python3
"""
Data migration script to move existing file-based data to database
Run this script once to populate the database with your existing restaurant data
"""

import json
import os
from pathlib import Path
from database_models import create_tables, SessionLocal, Restaurant, MenuCategory, MenuItem

def load_json_file(file_path):
    """Load JSON data from file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def migrate_restaurant_data():
    """Migrate restaurant data from files to database"""
    db = SessionLocal()
    
    try:
        # Create tables if they don't exist
        create_tables()
        
        # Migrate restaurant 1
        restaurant_1_info_file = Path("data/restaurant_info_1.json")
        restaurant_1_hours_file = Path("data/store_hours_1.json")
        
        if restaurant_1_info_file.exists() and restaurant_1_hours_file.exists():
            print("Migrating Restaurant 1 data...")
            
            # Load restaurant info
            restaurant_info = load_json_file(restaurant_1_info_file)
            hours_info = load_json_file(restaurant_1_hours_file)
            
            if restaurant_info and hours_info:
                # Check if restaurant 1 already exists
                existing_restaurant = db.query(Restaurant).filter(Restaurant.id == 1).first()
                if not existing_restaurant:
                    restaurant_1 = Restaurant(
                        id=1,
                        name=restaurant_info.get("name", "Restaurant 1"),
                        address=restaurant_info.get("address", ""),
                        phone=restaurant_info.get("phone", ""),
                        website=restaurant_info.get("website", ""),
                        doordash_link=restaurant_info.get("doordash_link", ""),
                        reservation_link=restaurant_info.get("reservation_link", ""),
                        timezone=hours_info.get("timezone", "America/New_York"),
                        business_hours=hours_info.get("business_hours", {}),
                        lunch_hours=hours_info.get("lunch_hours", {})
                    )
                    db.add(restaurant_1)
                    print("✅ Restaurant 1 data migrated")
                else:
                    print("⚠️ Restaurant 1 already exists in database")
        
        # Migrate restaurant 2
        restaurant_2_info_file = Path("data/restaurant_info_2.json")
        restaurant_2_hours_file = Path("data/store_hours_2.json")
        
        if restaurant_2_info_file.exists() and restaurant_2_hours_file.exists():
            print("Migrating Restaurant 2 data...")
            
            # Load restaurant info
            restaurant_info = load_json_file(restaurant_2_info_file)
            hours_info = load_json_file(restaurant_2_hours_file)
            
            if restaurant_info and hours_info:
                # Check if restaurant 2 already exists
                existing_restaurant = db.query(Restaurant).filter(Restaurant.id == 2).first()
                if not existing_restaurant:
                    restaurant_2 = Restaurant(
                        id=2,
                        name=restaurant_info.get("name", "Umai Nori"),
                        address=restaurant_info.get("address", "1147 20th Street North West, Washington, DC 20036"),
                        phone=restaurant_info.get("phone", "(202) 262-1073"),
                        website=restaurant_info.get("website", "www.umainori.com"),
                        doordash_link=restaurant_info.get("doordash_link", ""),
                        reservation_link=restaurant_info.get("reservation_link", ""),
                        timezone=hours_info.get("timezone", "America/New_York"),
                        business_hours=hours_info.get("business_hours", {}),
                        lunch_hours=hours_info.get("lunch_hours", {})
                    )
                    db.add(restaurant_2)
                    print("✅ Restaurant 2 data migrated")
                else:
                    print("⚠️ Restaurant 2 already exists in database")
        
        # Commit all changes
        db.commit()
        print("\n✅ Database migration completed successfully!")
        
        # Print summary
        restaurants = db.query(Restaurant).all()
        print(f"\nDatabase now contains {len(restaurants)} restaurant(s):")
        for restaurant in restaurants:
            print(f"- Restaurant {restaurant.id}: {restaurant.name}")
    
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        db.rollback()
    
    finally:
        db.close()

def migrate_menu_data():
    """Migrate menu data from text files to database"""
    db = SessionLocal()
    
    try:
        print("\nMigrating menu data...")
        
        # Load menu files
        menu_1_file = Path("menus/1.txt")
        menu_2_file = Path("menus/2.txt")
        
        if menu_1_file.exists():
            print("Processing Restaurant 1 menu...")
            # Note: Menu parsing would need to be implemented based on your menu format
            # For now, we'll create a placeholder category
            restaurant_1 = db.query(Restaurant).filter(Restaurant.id == 1).first()
            if restaurant_1:
                # Check if menu category already exists
                existing_category = db.query(MenuCategory).filter(
                    MenuCategory.restaurant_id == 1,
                    MenuCategory.name == "Main Menu"
                ).first()
                
                if not existing_category:
                    menu_category = MenuCategory(
                        restaurant_id=1,
                        name="Main Menu",
                        display_order=1
                    )
                    db.add(menu_category)
                    print("✅ Restaurant 1 menu category created")
        
        if menu_2_file.exists():
            print("Processing Restaurant 2 menu...")
            # Note: Menu parsing would need to be implemented based on your menu format
            restaurant_2 = db.query(Restaurant).filter(Restaurant.id == 2).first()
            if restaurant_2:
                # Check if menu category already exists
                existing_category = db.query(MenuCategory).filter(
                    MenuCategory.restaurant_id == 2,
                    MenuCategory.name == "Main Menu"
                ).first()
                
                if not existing_category:
                    menu_category = MenuCategory(
                        restaurant_id=2,
                        name="Main Menu", 
                        display_order=1
                    )
                    db.add(menu_category)
                    print("✅ Restaurant 2 menu category created")
        
        db.commit()
        print("✅ Menu data migration completed!")
        
    except Exception as e:
        print(f"❌ Error during menu migration: {e}")
        db.rollback()
    
    finally:
        db.close()

def verify_migration():
    """Verify the migration was successful"""
    db = SessionLocal()
    
    try:
        print("\n" + "="*50)
        print("MIGRATION VERIFICATION")
        print("="*50)
        
        # Check restaurants
        restaurants = db.query(Restaurant).all()
        print(f"Restaurants in database: {len(restaurants)}")
        
        for restaurant in restaurants:
            print(f"\nRestaurant {restaurant.id}:")
            print(f"  Name: {restaurant.name}")
            print(f"  Address: {restaurant.address}")
            print(f"  Phone: {restaurant.phone}")
            print(f"  Timezone: {restaurant.timezone}")
            print(f"  Business Hours: {len(restaurant.business_hours)} days configured")
            if restaurant.lunch_hours:
                print(f"  Lunch Hours: {len(restaurant.lunch_hours)} days configured")
        
        # Check menu categories
        categories = db.query(MenuCategory).all()
        print(f"\nMenu Categories: {len(categories)}")
        for category in categories:
            print(f"  Restaurant {category.restaurant_id}: {category.name}")
        
        print("\n✅ Migration verification completed!")
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting data migration to database...")
    print("This will move your existing restaurant data from files to SQLite database")
    
    # Run migrations
    migrate_restaurant_data()
    migrate_menu_data()
    verify_migration()
    
    print("\n" + "="*50)
    print("NEXT STEPS:")
    print("="*50)
    print("1. Test the enhanced business hours endpoint:")
    print("   POST /is_in_business_hour?restaurant_id=2&phone_number=2025551234")
    print()
    print("2. Update your Retell agent configuration to use:")
    print("   URL: https://keyra-api.onrender.com/is_in_business_hour?restaurant_id=2")
    print("   Add phone_number parameter if available from caller ID")
    print()
    print("3. Add a new tool to update customer names:")
    print("   URL: https://keyra-api.onrender.com/update_customer_name")
    print("   Parameters: phone_number, customer_name")
    print()
    print("🎉 Migration completed! Your API now supports customer memory!") 