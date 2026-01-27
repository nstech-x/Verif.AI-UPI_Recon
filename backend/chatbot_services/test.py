"""
Test script for Chatbot API
Run this after starting the server with: uvicorn app:app --reload
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def print_response(title, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"TEST: {title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))


def test_health_check():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print_response("Health Check", response)


def test_stats():
    """Test statistics endpoint"""
    response = requests.get(f"{BASE_URL}/api/v1/stats")
    print_response("Statistics", response)


def test_valid_rrn_found():
    """Test with valid RRN that exists"""
    response = requests.get(
        f"{BASE_URL}/api/v1/chatbot",
        params={"rrn": "636397811101708"}
    )
    print_response("Valid RRN (Found)", response)


def test_valid_rrn_not_found():
    """Test with valid RRN that doesn't exist"""
    response = requests.get(
        f"{BASE_URL}/api/v1/chatbot",
        params={"rrn": "999999999999"}
    )
    print_response("Valid RRN (Not Found)", response)


def test_invalid_rrn():
    """Test with invalid RRN format"""
    response = requests.get(
        f"{BASE_URL}/api/v1/chatbot",
        params={"rrn": "12345"}  # Only 5 digits
    )
    print_response("Invalid RRN Format", response)


def test_valid_txn_id():
    """Test with valid transaction ID"""
    response = requests.get(
        f"{BASE_URL}/api/v1/chatbot",
        params={"txn_id": "TXN001"}
    )
    print_response("Valid Transaction ID", response)


def test_no_parameters():
    """Test with no parameters"""
    response = requests.get(f"{BASE_URL}/api/v1/chatbot")
    print_response("No Parameters", response)


def test_partial_match():
    """Test transaction with partial match"""
    response = requests.get(
        f"{BASE_URL}/api/v1/chatbot",
        params={"rrn": "987654321098"}
    )
    print_response("Partial Match Transaction", response)


def test_no_match():
    """Test transaction with no match"""
    response = requests.get(
        f"{BASE_URL}/api/v1/chatbot",
        params={"rrn": "456123789000"}
    )
    print_response("No Match Transaction", response)


def run_all_tests():
    """Run all test cases"""
    print("\n" + "🚀 STARTING CHATBOT API TESTS " + "🚀")
    
    try:
        # Basic endpoints
        test_health_check()
        test_stats()
        
        # Success cases
        test_valid_rrn_found()
        test_valid_txn_id()
        test_partial_match()
        test_no_match()
        
        # Error cases
        test_valid_rrn_not_found()
        test_invalid_rrn()
        test_no_parameters()
        
        print("\n" + "✅ ALL TESTS COMPLETED " + "✅")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to API server")
        print("Make sure the server is running with: uvicorn app:app --reload")
    except Exception as e:
        print(f"\n❌ Test error: {e}")


if __name__ == "__main__":
    run_all_tests()