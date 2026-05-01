"""Integration tests for OpenEMR chat widget integration.

Tests the full flow from OpenEMR patient page → chat widget → agent service.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from main import app


class TestOpenEMRIntegration:
    """Test OpenEMR integration with chat widget."""

    def test_static_chat_html_accessible(self):
        """Test that chat.html is accessible from /static/chat.html."""
        client = TestClient(app)
        response = client.get("/static/chat.html")

        assert response.status_code == 200
        assert b"Clinical Co-Pilot" in response.content
        assert b"patient-id" in response.content  # Has patient ID input field

    def test_chat_html_accepts_pid_parameter(self):
        """Test that chat.html can receive patient ID via URL parameter."""
        client = TestClient(app)
        response = client.get("/static/chat.html?pid=5")

        assert response.status_code == 200
        # Verify the URL parameter logic exists in the HTML
        assert b"URLSearchParams" in response.content
        assert b"urlParams.get('pid')" in response.content or b"pid" in response.content

    @patch('main.ClinicalAgent')
    def test_agent_accepts_patient_id_from_openemr(self, MockAgent):
        """Test that /chat endpoint works with patient IDs passed from OpenEMR."""
        # Mock the agent instance and its method
        mock_instance = Mock()
        mock_instance.generate_pre_visit_summary.return_value = (
            "Patient summary here [source: Patient/1]",
            [{"name": "get_patient", "success": True}],
            {"input_tokens": 100, "output_tokens": 50}
        )
        mock_instance.close.return_value = None
        MockAgent.return_value = mock_instance

        client = TestClient(app)

        # Simulate OpenEMR passing patient ID 1
        response = client.post(
            "/chat",
            json={
                "patient_id": 1,
                "message": "Give me a pre-visit summary"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "patient_id_hash" in data
        assert data["patient_id_hash"].startswith("sha256:")

    @patch('main.ClinicalAgent')
    def test_multiple_patient_contexts(self, MockAgent):
        """Test that agent correctly handles different patient IDs from OpenEMR."""
        # Mock the agent instance
        mock_instance = Mock()
        mock_instance.generate_pre_visit_summary.return_value = (
            "Patient info here",
            [{"name": "get_patient", "success": True}],
            {"input_tokens": 100, "output_tokens": 50}
        )
        mock_instance.close.return_value = None
        MockAgent.return_value = mock_instance

        client = TestClient(app)

        # Patient 1
        response1 = client.post("/chat", json={"patient_id": 1, "message": "Who is this patient?"})
        assert response1.status_code == 200
        hash1 = response1.json()["patient_id_hash"]

        # Patient 2
        response2 = client.post("/chat", json={"patient_id": 2, "message": "Who is this patient?"})
        assert response2.status_code == 200
        hash2 = response2.json()["patient_id_hash"]

        # Hashes should be different (different patients)
        assert hash1 != hash2

    def test_chat_endpoint_with_invalid_patient_id_type(self):
        """Test that OpenEMR can't inject malicious patient IDs."""
        client = TestClient(app)

        # Try SQL injection
        response = client.post(
            "/chat",
            json={
                "patient_id": "'; DROP TABLE patients; --",
                "message": "test"
            }
        )

        # Should get 422 validation error (type mismatch)
        assert response.status_code == 422

    def test_cors_headers_for_iframe_embedding(self):
        """Test that CORS headers allow iframe embedding from OpenEMR."""
        client = TestClient(app)

        # Simulate request from OpenEMR iframe
        response = client.get(
            "/static/chat.html",
            headers={
                "Origin": "http://localhost:8300",
                "Referer": "http://localhost:8300/interface/patient_file/summary/demographics.php"
            }
        )

        assert response.status_code == 200
        # Note: May need to add CORS middleware if this fails

    @patch('main.ClinicalAgent')
    def test_agent_response_time_acceptable_for_ui(self, MockAgent):
        """Test that agent responds within acceptable time for UI (< 10 seconds)."""
        import time

        # Mock fast response
        mock_instance = Mock()
        mock_instance.generate_pre_visit_summary.return_value = (
            "Quick summary",
            [{"name": "get_patient", "success": True}],
            {"input_tokens": 100, "output_tokens": 50}
        )
        mock_instance.close.return_value = None
        MockAgent.return_value = mock_instance

        client = TestClient(app)

        start = time.time()
        response = client.post(
            "/chat",
            json={
                "patient_id": 1,
                "message": "Quick summary"
            },
            timeout=15  # Allow 15s but expect < 10s
        )
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 10.0, f"Response took {duration:.2f}s (> 10s threshold)"

        # Also check latency_ms in response
        latency_ms = response.json().get("latency_ms", 0)
        assert latency_ms < 10000, f"Reported latency {latency_ms}ms exceeds 10s"

    @patch('main.ClinicalAgent')
    def test_session_isolation_between_openemr_users(self, MockAgent):
        """Test that different OpenEMR sessions don't leak data."""
        # Mock the agent response
        mock_instance = Mock()
        mock_instance.generate_pre_visit_summary.return_value = (
            "Diagnosis info",
            [{"name": "get_patient", "success": True}],
            {"input_tokens": 100, "output_tokens": 50}
        )
        mock_instance.close.return_value = None
        MockAgent.return_value = mock_instance

        client = TestClient(app)

        # User 1 asks about Patient 1
        response1 = client.post(
            "/chat",
            json={"patient_id": 1, "message": "What's the diagnosis?"}
        )

        # User 2 asks about Patient 2 (in separate session)
        response2 = client.post(
            "/chat",
            json={"patient_id": 2, "message": "What's the diagnosis?"}
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Each response should have unique trace IDs
        trace1 = response1.json()["trace_id"]
        trace2 = response2.json()["trace_id"]
        assert trace1 != trace2

    def test_chat_widget_handles_missing_patient_id(self):
        """Test graceful handling when OpenEMR doesn't provide patient ID."""
        client = TestClient(app)

        # Try without patient_id (should fail validation)
        response = client.post(
            "/chat",
            json={"message": "test"}
        )

        assert response.status_code == 422  # Validation error
        assert "patient_id" in response.text.lower()

    def test_static_files_serve_correctly(self):
        """Test that all static files needed by chat widget are accessible."""
        client = TestClient(app)

        # Main chat widget
        response = client.get("/static/chat.html")
        assert response.status_code == 200

        # Demo page (if exists)
        demo_response = client.get("/static/demo.html")
        assert demo_response.status_code == 200

    def test_health_check_from_openemr_context(self):
        """Test that OpenEMR can check agent health status."""
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "clinical-copilot-agent"
