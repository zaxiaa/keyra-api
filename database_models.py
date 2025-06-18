from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_call_at = Column(DateTime, nullable=True)
    preferred_pickup_time = Column(String(10), nullable=True)  # e.g., "ASAP", "30 min"
    notes = Column(Text, nullable=True)  # Special preferences, allergies, etc.
    
    # Relationships
    orders = relationship("Order", back_populates="customer")

class Restaurant(Base):
    __tablename__ = "restaurants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    address = Column(Text, nullable=False)
    phone = Column(String(20), nullable=False)
    website = Column(String(200), nullable=True)
    doordash_link = Column(String(500), nullable=True)
    reservation_link = Column(String(500), nullable=True)
    timezone = Column(String(50), default="America/New_York")
    
    # Business hours stored as JSON
    business_hours = Column(JSON, nullable=False)  # Store the complex schedule
    lunch_hours = Column(JSON, nullable=True)
    
    # Relationships
    menu_categories = relationship("MenuCategory", back_populates="restaurant")

class MenuCategory(Base):
    __tablename__ = "menu_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "Starter Menu", "Sushi", etc.
    display_order = Column(Integer, default=0)
    is_lunch_only = Column(Boolean, default=False)
    
    # Relationships
    restaurant = relationship("Restaurant", back_populates="menu_categories")
    menu_items = relationship("MenuItem", back_populates="category")

class MenuItem(Base):
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=False)
    item_id = Column(String(20), nullable=False)  # e.g., "1319"
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True)
    
    # Relationships
    category = relationship("MenuCategory", back_populates="menu_items")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    order_data = Column(JSON, nullable=False)  # Store the complete order JSON
    total_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="orders")

# Database setup with PostgreSQL support
def get_database_url():
    """Get database URL from environment variables"""
    # Try to get PostgreSQL URL from various environment variable names
    database_url = (
        os.getenv("DATABASE_URL") or 
        os.getenv("POSTGRES_URL") or 
        os.getenv("POSTGRESQL_URL") or
        os.getenv("DB_URL")
    )
    
    if database_url:
        # Handle Render.com PostgreSQL URLs that might start with postgres://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url
    
    # Development fallback - SQLite
    return "sqlite:///./restaurant.db"

DATABASE_URL = get_database_url()

# Create engine with appropriate settings for PostgreSQL vs SQLite
if DATABASE_URL.startswith("postgresql://"):
    # PostgreSQL settings
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False  # Set to True for SQL debugging
    )
else:
    # SQLite settings (for local development)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)
    print(f"✅ Database tables created/verified using: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else DATABASE_URL}")

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_database_connection():
    """Test database connection and return info"""
    try:
        db = SessionLocal()
        
        # Test basic connection
        if DATABASE_URL.startswith("postgresql://"):
            # PostgreSQL-specific test
            result = db.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            db_type = "PostgreSQL"
            db_info = version.split(' ')[0:2]
        else:
            # SQLite test
            result = db.execute(text("SELECT sqlite_version()"))
            version = result.fetchone()[0]
            db_type = "SQLite"
            db_info = [f"SQLite {version}"]
        
        db.close()
        return {
            "status": "connected",
            "database_type": db_type,
            "version": db_info,
            "url_masked": DATABASE_URL.split('@')[0] + "@***" if '@' in DATABASE_URL else DATABASE_URL
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "database_type": "Unknown",
            "url_masked": DATABASE_URL.split('@')[0] + "@***" if '@' in DATABASE_URL else DATABASE_URL
        } 