import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_missing_auth_header_metrics():
    """Edge Case: Unauthorized access to an endpoint that might require auth."""
    # Note: If /metrics is completely unprotected, this might succeed,
    # but we are testing the application's response robustness.
    response = client.get("/metrics")
    # Prometheus metrics usually return 200, but if we protect it, it would be 401/403.
    # In VOYA it's public inside the cluster, so 200 is expected but it's an edge load test.
    assert response.status_code == 200

def test_invalid_uuid_format():
    """Edge Case: Passing non-UUID string where UUID is expected."""
    response = client.get("/api/v1/users/not-a-valid-uuid")
    # Should be 404 (route not found) or 422 (validation error)
    assert response.status_code in (404, 422)

def test_extreme_pagination_params():
    """Edge Case: Out of bounds pagination limits."""
    # Passing an extremely large integer to limit
    response = client.get("/api/v1/sessions?skip=0&limit=999999999999999")
    # Typically 422 Unprocessable Entity if pydantic validates max value
    # or 200/401/403 depending on auth state.
    assert response.status_code in (401, 403, 404, 422, 200)

def test_negative_pagination_params():
    """Edge Case: Negative numbers in pagination."""
    response = client.get("/api/v1/sessions?skip=-5&limit=-10")
    # Typically 422 Unprocessable Entity
    assert response.status_code in (401, 403, 404, 422)

def test_malformed_json_payload():
    """Edge Case: Sending invalid JSON body."""
    response = client.post(
        "/api/v1/auth/login",
        content="this is not valid json",  # raw body; httpx deprecates data= for this
        headers={"Content-Type": "application/json"}
    )
    # FastAPI automatically handles malformed JSON with 422
    assert response.status_code == 422
