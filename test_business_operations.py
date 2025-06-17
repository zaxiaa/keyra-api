#!/usr/bin/env python3

import json
import requests
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8001"
RESTAURANT_ID = "1"

def test_business_hours():
    """Test business hours endpoint"""
    print("=== Testing Business Hours ===")
    response = requests.get(f"{BASE_URL}/is-in-business-hour?restaurant_id={RESTAURANT_ID}")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_lunch_hours():
    """Test lunch hours endpoint"""
    print("=== Testing Lunch Hours ===")
    response = requests.get(f"{BASE_URL}/is-in-lunch-hour?restaurant_id={RESTAURANT_ID}")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_order_total():
    """Test order total calculation"""
    print("=== Testing Order Total ===")
    
    # Sample order data
    order_data = {
        "delivery_fee": 3.50,
        "customer_address": "123 Main St, City, State 12345",
        "execution_message": "please wait, let me calculate the total",
        "order_notes": "Extra napkins please",
        "customer_phone": "555-123-4567",
        "tip_amount": 5.00,
        "customer_name": "John Doe",
        "pick_up_time": "6:30 PM",
        "order_type": "dine-in",
        "order_items": [
            {
                "item_name": "Cheeseburger",
                "item_base_price": 12.99,
                "item_quantity": 2,
                "special_instructions": "No pickles",
                "modifiers": [
                    {
                        "modifier_name": "Extra Cheese",
                        "modifier_quantity": 1,
                        "modifier_price": 1.50
                    },
                    {
                        "modifier_name": "Bacon",
                        "modifier_quantity": 2,
                        "modifier_price": 2.00
                    }
                ]
            },
            {
                "item_name": "French Fries",
                "item_base_price": 4.99,
                "item_quantity": 1,
                "modifiers": [
                    {
                        "modifier_name": "Large Size",
                        "modifier_quantity": 1,
                        "modifier_price": 1.00
                    }
                ]
            },
            {
                "item_name": "Soda",
                "item_base_price": 2.99,
                "item_quantity": 2
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/get-order-total?restaurant_id={RESTAURANT_ID}",
        json=order_data
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_store_hours_config():
    """Test store hours configuration endpoints"""
    print("=== Testing Store Hours Configuration ===")
    
    # Get current store hours
    response = requests.get(f"{BASE_URL}/store-hours/{RESTAURANT_ID}")
    print(f"Current Store Hours - Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def main():
    """Run all tests"""
    print(f"Testing Business Operations API at {BASE_URL}")
    print(f"Restaurant ID: {RESTAURANT_ID}")
    print(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    try:
        test_business_hours()
        test_lunch_hours()
        test_order_total()
        test_store_hours_config()
        print("All tests completed!")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API server.")
        print("Make sure the server is running with: python business_operations.py")
    except Exception as e:
        print(f"Error running tests: {str(e)}")

if __name__ == "__main__":
    main() 