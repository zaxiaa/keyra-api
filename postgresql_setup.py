#!/usr/bin/env python3
"""
PostgreSQL Setup and Migration Script
This script helps set up PostgreSQL and migrate data from SQLite to PostgreSQL
"""

import os
import json
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database_models import Base, SessionLocal, Restaurant, Customer, MenuCategory, get_database_url, test_database_connection

def check_postgresql_requirements():
    """Check if PostgreSQL dependencies are installed"""
    try:
        import psycopg2
        print("✅ psycopg2-binary is installed")
        return True
    except ImportError:
        print("❌ psycopg2-binary not found. Install with: pip install psycopg2-binary")
        return False

def validate_postgresql_url(database_url):
    """Validate PostgreSQL connection string"""
    if not database_url or not database_url.startswith("postgresql://"):
        print("❌ Invalid PostgreSQL URL. Expected format:")
        print("   postgresql://username:password@host:port/database")
        print("   Example: postgresql://user:pass@localhost:5432/restaurant_db")
        return False
    
    try:
        # Test connection
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ PostgreSQL connection successful!")
            print(f"   Database: {version.split(' ')[0]} {version.split(' ')[1]}")
            return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {str(e)}")
        return False

def setup_postgresql_database():
    """Create database tables in PostgreSQL"""
    try:
        database_url = get_database_url()
        
        if not database_url.startswith("postgresql://"):
            print("❌ PostgreSQL DATABASE_URL not found in environment variables.")
            print("\nTo set up PostgreSQL, you need to:")
            print("1. Set one of these environment variables:")
            print("   - DATABASE_URL")
            print("   - POSTGRES_URL") 
            print("   - POSTGRESQL_URL")
            print("   - DB_URL")
            print("\n2. Format: postgresql://username:password@host:port/database")
            print("\nFor Render.com, this is automatically provided.")
            return False
        
        print(f"🔗 Connecting to PostgreSQL...")
        print(f"   URL: {database_url.split('@')[0]}@***")
        
        if not validate_postgresql_url(database_url):
            return False
        
        # Create tables
        print("🛠️  Creating database tables...")
        Base.metadata.create_all(bind=create_engine(database_url))
        print("✅ Database tables created successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up PostgreSQL database: {str(e)}")
        return False

def migrate_sqlite_to_postgresql():
    """Migrate data from SQLite to PostgreSQL"""
    try:
        # Check if SQLite database exists
        sqlite_db = Path("restaurant.db")
        if not sqlite_db.exists():
            print("ℹ️  No SQLite database found to migrate from")
            return True
        
        print("🔄 Migrating data from SQLite to PostgreSQL...")
        
        # Connect to SQLite
        sqlite_engine = create_engine("sqlite:///./restaurant.db")
        SqliteSession = sessionmaker(bind=sqlite_engine)
        sqlite_session = SqliteSession()
        
        # Connect to PostgreSQL
        pg_database_url = get_database_url()
        pg_engine = create_engine(pg_database_url)
        PgSession = sessionmaker(bind=pg_engine)
        pg_session = PgSession()
        
        # Migrate Restaurants
        sqlite_restaurants = sqlite_session.query(Restaurant).all()
        for restaurant in sqlite_restaurants:
            # Check if restaurant already exists in PostgreSQL
            existing = pg_session.query(Restaurant).filter(Restaurant.id == restaurant.id).first()
            if not existing:
                new_restaurant = Restaurant(
                    id=restaurant.id,
                    name=restaurant.name,
                    address=restaurant.address,
                    phone=restaurant.phone,
                    website=restaurant.website,
                    doordash_link=restaurant.doordash_link,
                    reservation_link=restaurant.reservation_link,
                    timezone=restaurant.timezone,
                    business_hours=restaurant.business_hours,
                    lunch_hours=restaurant.lunch_hours
                )
                pg_session.add(new_restaurant)
                print(f"   ✅ Migrated restaurant: {restaurant.name}")
            else:
                print(f"   ⚠️  Restaurant {restaurant.name} already exists")
        
        # Migrate Customers
        sqlite_customers = sqlite_session.query(Customer).all()
        for customer in sqlite_customers:
            existing = pg_session.query(Customer).filter(Customer.phone_number == customer.phone_number).first()
            if not existing:
                new_customer = Customer(
                    phone_number=customer.phone_number,
                    name=customer.name,
                    email=customer.email,
                    created_at=customer.created_at,
                    updated_at=customer.updated_at,
                    last_call_at=customer.last_call_at,
                    preferred_pickup_time=customer.preferred_pickup_time,
                    notes=customer.notes
                )
                pg_session.add(new_customer)
                print(f"   ✅ Migrated customer: {customer.name or customer.phone_number}")
            else:
                print(f"   ⚠️  Customer {customer.phone_number} already exists")
        
        # Migrate Menu Categories
        sqlite_categories = sqlite_session.query(MenuCategory).all()
        for category in sqlite_categories:
            existing = pg_session.query(MenuCategory).filter(
                MenuCategory.restaurant_id == category.restaurant_id,
                MenuCategory.name == category.name
            ).first()
            if not existing:
                new_category = MenuCategory(
                    restaurant_id=category.restaurant_id,
                    name=category.name,
                    display_order=category.display_order,
                    is_lunch_only=category.is_lunch_only
                )
                pg_session.add(new_category)
                print(f"   ✅ Migrated menu category: {category.name}")
            else:
                print(f"   ⚠️  Menu category {category.name} already exists")
        
        # Commit all changes
        pg_session.commit()
        
        # Close sessions
        sqlite_session.close()
        pg_session.close()
        
        print("✅ Data migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        return False

def verify_postgresql_setup():
    """Verify PostgreSQL setup and data"""
    try:
        print("\n" + "="*60)
        print("POSTGRESQL SETUP VERIFICATION")
        print("="*60)
        
        # Test connection
        db_info = test_database_connection()
        print(f"Database Status: {db_info['status']}")
        print(f"Database Type: {db_info.get('database_type', 'Unknown')}")
        if 'version' in db_info:
            print(f"Version: {' '.join(db_info['version'])}")
        print(f"Connection URL: {db_info.get('url_masked', 'Unknown')}")
        
        if db_info['status'] != 'connected':
            print(f"❌ Connection Error: {db_info.get('error', 'Unknown error')}")
            return False
        
        # Check tables and data
        pg_session = SessionLocal()
        
        restaurants = pg_session.query(Restaurant).all()
        customers = pg_session.query(Customer).all()
        categories = pg_session.query(MenuCategory).all()
        
        print(f"\nData Summary:")
        print(f"  Restaurants: {len(restaurants)}")
        print(f"  Customers: {len(customers)}")
        print(f"  Menu Categories: {len(categories)}")
        
        for restaurant in restaurants:
            print(f"\n  Restaurant {restaurant.id}: {restaurant.name}")
            print(f"    Address: {restaurant.address}")
            print(f"    Phone: {restaurant.phone}")
        
        for customer in customers:
            name = customer.name or "Unknown"
            print(f"\n  Customer: {name} ({customer.phone_number})")
            print(f"    Last Call: {customer.last_call_at}")
        
        pg_session.close()
        
        print("\n✅ PostgreSQL setup verification completed!")
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("🐘 PostgreSQL Setup for Keyra Restaurant API")
    print("=" * 50)
    
    # Check requirements
    if not check_postgresql_requirements():
        print("\n❌ Setup failed: Missing requirements")
        return
    
    # Setup database
    if not setup_postgresql_database():
        print("\n❌ Setup failed: Could not create database")
        return
    
    # Migrate data
    if not migrate_sqlite_to_postgresql():
        print("\n❌ Setup failed: Data migration error")
        return
    
    # Verify setup
    if not verify_postgresql_setup():
        print("\n❌ Setup failed: Verification error")
        return
    
    print("\n" + "="*60)
    print("🎉 POSTGRESQL SETUP COMPLETED SUCCESSFULLY!")
    print("="*60)
    print("\nNext steps:")
    print("1. Your API now uses PostgreSQL for customer memory")
    print("2. Deploy your updated code to Render")
    print("3. Test the enhanced endpoints:")
    print("   GET /test-db")
    print("   GET /health")
    print("   POST /is_in_business_hour?restaurant_id=2&phone_number=2025551234")
    print("\n4. Update your Retell AI agent configuration")
    print("   See RETELL_AGENT_UPDATES.md for details")

if __name__ == "__main__":
    main() 