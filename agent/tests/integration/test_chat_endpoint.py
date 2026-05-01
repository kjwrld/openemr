"""Integration tests for /chat endpoint."""

import pytest
from fastapi.testclient import TestClient

# Note: These are integration tests that would require mocking the Anthropic API
# For now, we'll create the structure. Full integration tests would need API mocks.


@pytest.mark.integration
class TestChatEndpoint:
    """Test /chat endpoint integration."""

    def test_health_check(self):
        """Test health check endpoint."""
        from main import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "clinical-copilot-agent"

    def test_chat_request_schema(self):
        """Test that /chat validates request schema."""
        from main import app

        client = TestClient(app)

        # Missing required fields should return 422
        response = client.post("/chat", json={})
        assert response.status_code == 422

    def test_chat_invalid_patient_id(self):
        """Test /chat with invalid patient ID type."""
        from main import app

        client = TestClient(app)

        # String patient_id should fail validation
        response = client.post(
            "/chat",
            json={"patient_id": "not-a-number", "message": "test"},
        )
        assert response.status_code == 422
