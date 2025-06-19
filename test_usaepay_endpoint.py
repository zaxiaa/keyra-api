#!/usr/bin/env python3
"""
Test script for the USAePay credit card charging endpoint
"""

import requests
import json
import os

# Test configuration
BASE_URL = "http://localhost:8000"
ENDPOINT = "/charge-credit-card"

def test_credit_card_charge():
    """Test the credit card charging endpoint"""
    
    # Test data - using USAePay test credit card
    test_request = {
        "base_charge_amount": 25.99,
        "credit_card_number": "4444333322221111",  # USAePay test card
        "credit_card_cvv": "123",
        "credit_card_zip_code": "12345",
        "credit_card_expiration_date": "1225",  # December 2025
        "tip_amount": 5.00,
        "cardholder_name": "John Doe",
        "billing_street": "123 Main St"
    }
    
    print("Testing USAePay Credit Card Endpoint")
    print("=" * 50)
    print(f"URL: {BASE_URL}{ENDPOINT}")
    print(f"Request Data:")
    print(json.dumps(test_request, indent=2))
    print("\n" + "=" * 50)
    
    try:
        # Make the request
        response = requests.post(
            f"{BASE_URL}{ENDPOINT}",
            json=test_request,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"HTTP Status Code: {response.status_code}")
        
        # Parse response
        result = response.json()
        print(f"Response:")
        print(json.dumps(result, indent=2))
        
        # Check results
        if response.status_code == 200:
            if result.get('success'):
                print("\n✅ SUCCESS: Payment processed successfully!")
                print(f"   Transaction ID: {result.get('transaction_id')}")
                print(f"   Auth Code: {result.get('auth_code')}")
                print(f"   Total Charged: ${result.get('total_amount')}")
            else:
                print("\n❌ DECLINED: Payment was declined")
                print(f"   Reason: {result.get('error_message')}")
        else:
            print(f"\n❌ ERROR: HTTP {response.status_code}")
            print(f"   Message: {result.get('detail', 'Unknown error')}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ CONNECTION ERROR: Could not connect to the server")
        print("   Make sure the FastAPI server is running on localhost:8000")
        print("   Run: python main.py")
        
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")

def test_validation_errors():
    """Test the endpoint with invalid data to check validation"""
    
    print("\n" + "=" * 50)
    print("Testing Validation Errors")
    print("=" * 50)
    
    # Test with missing required fields
    invalid_request = {
        "base_charge_amount": 25.99,
        # Missing credit card info and cardholder_name
        "tip_amount": 5.00
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}{ENDPOINT}",
            json=invalid_request,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"HTTP Status Code: {response.status_code}")
        result = response.json()
        print(f"Validation Error Response:")
        print(json.dumps(result, indent=2))
        
        if response.status_code == 422:
            print("\n✅ VALIDATION: Properly rejected invalid request")
        else:
            print("\n❌ VALIDATION: Should have returned 422 for invalid request")
            
    except Exception as e:
        print(f"\n❌ VALIDATION TEST ERROR: {str(e)}")

def check_environment():
    """Check if required environment variables are set"""
    
    print("Checking Environment Configuration")
    print("=" * 50)
    
    api_key = os.getenv("USAEPAY_API_KEY")
    api_pin = os.getenv("USAEPAY_API_PIN")
    environment = os.getenv("USAEPAY_ENVIRONMENT", "sandbox")
    
    print(f"USAEPAY_API_KEY: {'✅ Set' if api_key else '❌ Not Set'}")
    print(f"USAEPAY_API_PIN: {'✅ Set' if api_pin else '⚠️  Not Set (optional)'}")
    print(f"USAEPAY_ENVIRONMENT: {environment}")
    
    if not api_key:
        print("\n❌ WARNING: USAEPAY_API_KEY not set!")
        print("   The endpoint will return a configuration error.")
        print("   Set your USAePay API key:")
        print("   export USAEPAY_API_KEY=your_api_key_here")
        return False
    
    return True

if __name__ == "__main__":
    print("USAePay Endpoint Test Script")
    print("=" * 50)
    
    # Check environment first
    env_ok = check_environment()
    print()
    
    # Run tests
    if env_ok:
        test_credit_card_charge()
        test_validation_errors()
    else:
        print("Skipping tests due to missing environment configuration.")
        print("Please set USAEPAY_API_KEY and try again.")
    
    print("\n" + "=" * 50)
    print("Test completed!") 