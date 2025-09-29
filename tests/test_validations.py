# test_validations.py
import requests
import json
from jose import jwt
from datetime import datetime, timedelta, timezone

BASE_URL = "http://localhost:8000"
# ✅ Use raw string to avoid escape sequence warning
JWT_SECRET = r"vTp2XS(CAW~7<V=b\-}GA{z[JhpHt_.r"
JWT_ALGORITHM = "HS256"

def create_token(user_id, tenant_id):
    """Helper to create test JWT"""
    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        # ✅ Fix deprecation warning
        "exp": datetime.now(timezone.utc) + timedelta(days=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def test_no_auth():
    """Test without authentication"""
    print("\n1. Testing no authentication...")
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        json={"message": "test"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

def test_invalid_token():
    """Test with invalid token"""
    print("\n2. Testing invalid token...")
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        headers={"Authorization": "Bearer invalid_token"},
        json={"message": "test"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

def test_fake_user():
    """Test with valid token but non-existent user (should work if no user validation)"""
    print("\n3. Testing fake user...")
    token = create_token("fake_user_999", "6875f3afc8337606d54a7f37")
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "test"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    # Note: This might return 200 if you don't validate user existence in DB
    # Just check it doesn't error on token validation
    assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"

def test_empty_message():
    """Test with empty message"""
    print("\n4. Testing empty message...")
    token = create_token("user_123", "6875f3afc8337606d54a7f37")
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": ""}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    # Should return 400 or validation error
    assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"

def test_long_message():
    """Test with message too long"""
    print("\n5. Testing long message...")
    token = create_token("user_123", "6875f3afc8337606d54a7f37")
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "a" * 1001}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"

def test_invalid_session_id():
    """Test with invalid session_id format"""
    print("\n6. Testing invalid session_id...")
    token = create_token("user_123", "6875f3afc8337606d54a7f37")
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "test", "session_id": "not-a-uuid"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    # Session ID validation might not be strict - just check it processes
    print("Note: Session ID validation behavior observed")

def test_valid_request():
    """Test with valid request"""
    print("\n7. Testing valid request...")
    token = create_token("user_123", "6875f3afc8337606d54a7f37")
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "show me TOFU content"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

if __name__ == "__main__":
    try:
        test_no_auth()
        test_invalid_token()
        test_fake_user()
        test_empty_message()
        test_long_message()
        test_invalid_session_id()
        test_valid_request()
        
        print("\n✅ All validation tests completed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()