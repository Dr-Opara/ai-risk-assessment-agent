"""
Smoke tests for the health endpoint.

Run with:
    pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Reusable FastAPI test client."""
    return TestClient(app)


def test_health_endpoint_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_endpoint_returns_expected_payload(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    body = response.json()

    assert body.get("status") == "ok"
    assert "service" in body
    assert "version" in body


def test_health_endpoint_content_type(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers["content-type"].startswith("application/json")


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404