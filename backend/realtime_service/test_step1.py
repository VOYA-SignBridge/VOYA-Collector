"""
Test Step 1 implementation: POST /predict endpoint.

Tests:
1. Valid inference request
2. Malformed frames (wrong shape)
3. NaN payload rejection
4. Inf payload rejection
5. Wrong sequence length
6. Wrong feature dimension
7. Unknown model_id
8. Empty payload
9. Deterministic responses (same input → same output)
10. HTTP error codes
"""

import json
import sys
from pathlib import Path

import numpy as np

# Add backend to path for FastAPI app import
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

from app.main import create_app


def create_valid_frames() -> list:
    """Create a valid 60x126 frame sequence (all zeros)."""
    return [[0.0] * 126 for _ in range(60)]


def test_valid_inference():
    """Test: Valid inference request returns 200 with correct response shape."""
    app = create_app()
    client = TestClient(app)

    frames = create_valid_frames()
    payload = {"model_id": "hoa-de", "frames": frames}

    response = client.post("/predict", json=payload)
    print(f"✓ Valid inference: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    assert "label" in data, "Response missing 'label'"
    assert "confidence" in data, "Response missing 'confidence'"
    assert "label_key" in data, "Response missing 'label_key'"
    assert isinstance(data["confidence"], float), "confidence must be float"
    assert 0.0 <= data["confidence"] <= 1.0, f"confidence out of bounds: {data['confidence']}"
    print(f"  Response: label={data['label']}, confidence={data['confidence']:.4f}")


def test_determinism():
    """Test: Same input produces same output (determinism)."""
    app = create_app()
    client = TestClient(app)

    frames = create_valid_frames()
    payload = {"model_id": "hoa-de", "frames": frames}

    response1 = client.post("/predict", json=payload)
    response2 = client.post("/predict", json=payload)

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    assert data1["label"] == data2["label"], "Label changed between identical requests"
    assert data1["confidence"] == data2["confidence"], "Confidence changed between identical requests"
    assert data1["label_key"] == data2["label_key"], "Label key changed between identical requests"
    print(f"✓ Determinism (2x): identical requests produce identical responses")


def test_determinism_100x():
    """Test: Same input produces IDENTICAL output over 100 requests (strict determinism contract)."""
    app = create_app()
    client = TestClient(app)

    frames = create_valid_frames()
    payload = {"model_id": "hoa-de", "frames": frames}

    # First request is baseline
    response1 = client.post("/predict", json=payload)
    assert response1.status_code == 200
    baseline = response1.json()

    # 99 more requests must be identical
    for i in range(99):
        response = client.post("/predict", json=payload)
        assert response.status_code == 200, f"Request {i+2} returned {response.status_code}"

        data = response.json()
        assert data["label"] == baseline["label"], f"Label diverged at request {i+2}"
        assert data["confidence"] == baseline["confidence"], f"Confidence diverged at request {i+2}"
        assert data["label_key"] == baseline["label_key"], f"Label key diverged at request {i+2}"

    print(f"✓ Determinism (100x): 100 identical requests → 100 identical responses")


def test_wrong_sequence_length():
    """Test: Wrong sequence length (59 instead of 60) returns 422."""
    app = create_app()
    client = TestClient(app)

    frames = [[0.0] * 126 for _ in range(59)]
    payload = {"model_id": "hoa-de", "frames": frames}

    response = client.post("/predict", json=payload)
    print(f"✓ Wrong seq length (59): {response.status_code}")
    assert response.status_code == 422, f"Expected 422, got {response.status_code}"


def test_wrong_feature_dimension():
    """Test: Wrong feature dimension (125 instead of 126) returns 422."""
    app = create_app()
    client = TestClient(app)

    frames = [[0.0] * 125 for _ in range(60)]
    payload = {"model_id": "hoa-de", "frames": frames}

    response = client.post("/predict", json=payload)
    print(f"✓ Wrong feature dim (125): {response.status_code}")
    assert response.status_code == 422, f"Expected 422, got {response.status_code}"


def test_nan_payload():
    """Test: NaN values are rejected with 422."""
    app = create_app()
    client = TestClient(app)

    frames = create_valid_frames()
    frames[0][0] = float("nan")
    payload = {"model_id": "hoa-de", "frames": frames}

    response = client.post("/predict", json=payload)
    print(f"✓ NaN payload: {response.status_code}")
    assert response.status_code == 422, f"Expected 422, got {response.status_code}"


def test_inf_payload():
    """Test: Inf values are rejected with 422."""
    app = create_app()
    client = TestClient(app)

    frames = create_valid_frames()
    frames[0][0] = float("inf")
    payload = {"model_id": "hoa-de", "frames": frames}

    response = client.post("/predict", json=payload)
    print(f"✓ Inf payload: {response.status_code}")
    assert response.status_code == 422, f"Expected 422, got {response.status_code}"


def test_unknown_model_id():
    """Test: Unknown model_id returns 404."""
    app = create_app()
    client = TestClient(app)

    frames = create_valid_frames()
    payload = {"model_id": "nonexistent-model", "frames": frames}

    response = client.post("/predict", json=payload)
    print(f"✓ Unknown model_id: {response.status_code}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"


def test_empty_payload():
    """Test: Empty payload returns 422."""
    app = create_app()
    client = TestClient(app)

    response = client.post("/predict", json={})
    print(f"✓ Empty payload: {response.status_code}")
    assert response.status_code == 422, f"Expected 422, got {response.status_code}"


def test_health_endpoint():
    """Test: Health endpoint still works."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")
    print(f"✓ /health endpoint: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    assert data["status"] == "ok", "Health status not 'ok'"
    assert "model_count" in data, "Health response missing 'model_count'"
    print(f"  Models available: {data['model_count']}")


def test_models_endpoint():
    """Test: Models list endpoint still works."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/models")
    print(f"✓ /models endpoint: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    assert isinstance(data, list), "Models response should be a list"
    if data:
        m = data[0]
        assert "id" in m, "Model entry missing 'id'"
        assert "name" in m, "Model entry missing 'name'"
        print(f"  Example model: {m['id']} ({m['name']})")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("STEP 1 TEST SUITE: POST /predict endpoint")
    print("=" * 70 + "\n")

    tests = [
        ("Health endpoint", test_health_endpoint),
        ("Models endpoint", test_models_endpoint),
        ("Valid inference", test_valid_inference),
        ("Determinism (2x)", test_determinism),
        ("Determinism (100x) - STRICT CONTRACT", test_determinism_100x),
        ("Wrong sequence length", test_wrong_sequence_length),
        ("Wrong feature dimension", test_wrong_feature_dimension),
        ("NaN payload rejection", test_nan_payload),
        ("Inf payload rejection", test_inf_payload),
        ("Unknown model_id", test_unknown_model_id),
        ("Empty payload", test_empty_payload),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}: FAILED")
            print(f"  {e}\n")
            failed += 1
        except Exception as e:
            print(f"✗ {name}: ERROR")
            print(f"  {e}\n")
            failed += 1

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
