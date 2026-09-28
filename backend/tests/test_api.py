"""Unit and integration tests for Project LEX Backend."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns operational metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Setowa Evidence API"
    assert data["status"] == "online"
    assert "docs_url" in data


def test_health_check():
    """Verify /api/v1/health returns healthy state."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "mock_mode" in data


def test_mock_stats():
    """Verify showcase stats endpoint returns metrics list without ungrounded claims."""
    response = client.get("/api/v1/mock-stats")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert len(data["metrics"]) == 3
    labels = [m["label"] for m in data["metrics"]]
    assert "Response Latency" in labels
    assert "AI Accuracy" in labels
    for metric in data["metrics"]:
        assert "99.4" not in metric["value"]
    accuracy_metric = next(m for m in data["metrics"] if m["label"] == "AI Accuracy")
    assert "Demo" in accuracy_metric["value"] or "Synthetic" in accuracy_metric["trend"]



def test_analyze_mock_mode():
    """Verify reasoning endpoint processes prompt in mock mode."""
    payload = {
        "prompt": "Optimize customer support inquiry categorization",
        "task_type": "classification",
        "parameters": {"depth": "high"}
    }
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["task_type"] == "classification"
    assert "mock-engine" in data["source"]
    assert data["confidence"] > 0.9


def test_analyze_empty_prompt():
    """Verify validation handles empty prompt appropriately."""
    payload = {"prompt": "   "}
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 422
