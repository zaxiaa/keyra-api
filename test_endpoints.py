#!/usr/bin/env python3
"""
Simple test script to verify all business hours endpoints are working
"""

import requests
import json

BASE_URL = "http://localhost:8001"
RESTAURANT_ID = "1"

def test_endpoint(method, endpoint, description):
    """Test a single endpoint"""
    url = f"{BASE_URL}{endpoint}?restaurant_id={RESTAURANT_ID}"
    print(f"\n🧪 Testing {description}")
    print(f"   {method} {endpoint}?restaurant_id={RESTAURANT_ID}")
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url)
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data.get('is_in_business_hour', 'N/A')}")
            print(f"   Time: {data.get('current_time', 'N/A')}")
            print(f"   Hours: {data.get('business_hours', 'N/A')}")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   💥 Exception: {str(e)}")

def main():
    print("🔍 Testing All Business Hours Endpoints")
    print("=" * 50)
    
    # Test all business hours endpoints
    test_endpoint("GET", "/is-in-business-hour", "Business Hours (GET, singular)")
    test_endpoint("POST", "/is-in-business-hour", "Business Hours (POST, singular)")
    test_endpoint("GET", "/is_in_business_hours", "Business Hours (GET, plural)")
    test_endpoint("POST", "/is_in_business_hours", "Business Hours (POST, plural)")
    
    # Test root endpoint
    print(f"\n🔍 Testing Root Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"   GET / - Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Root OK: {response.json()}")
    except Exception as e:
        print(f"   💥 Root Error: {str(e)}")

if __name__ == "__main__":
    main() 