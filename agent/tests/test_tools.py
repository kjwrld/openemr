"""Unit tests for FHIR tools."""

import pytest
import respx
from httpx import Response

from tools import FHIRTools


@pytest.mark.unit
class TestFHIRTools:
    """Test FHIR tool functions."""

    @respx.mock
    def test_get_patient_success(self, sample_patient_fhir):
        """Test successful patient retrieval."""
        base_url = "http://test-fhir.example.com/fhir"
        respx.get(f"{base_url}/Patient/1").mock(return_value=Response(200, json=sample_patient_fhir))

        tools = FHIRTools(base_url=base_url, trace_id="test-trace")
        result = tools.get_patient(patient_id=1)

        assert result.success is True
        assert result.data is not None
        assert result.data["id"] == "1"
        assert result.source_id == "Patient/1"
        tools.close()

    @respx.mock
    def test_get_patient_not_found(self):
        """Test patient not found (404)."""
        base_url = "http://test-fhir.example.com/fhir"
        respx.get(f"{base_url}/Patient/999").mock(return_value=Response(404))

        tools = FHIRTools(base_url=base_url, trace_id="test-trace")
        result = tools.get_patient(patient_id=999)

        assert result.success is False
        assert result.error == "Resource not found"
        assert result.data is None
        tools.close()

    @respx.mock
    def test_get_recent_vitals_success(self, sample_vitals_fhir):
        """Test successful vitals retrieval."""
        base_url = "http://test-fhir.example.com/fhir"
        respx.get(f"{base_url}/Observation").mock(return_value=Response(200, json=sample_vitals_fhir))

        tools = FHIRTools(base_url=base_url, trace_id="test-trace")
        result = tools.get_recent_vitals(patient_id=1, count=3)

        assert result.success is True
        assert result.data is not None
        assert result.data["resourceType"] == "Bundle"
        assert len(result.data["entry"]) > 0
        tools.close()

    @respx.mock
    def test_get_active_medications_success(self, sample_medications_fhir):
        """Test successful medication retrieval."""
        base_url = "http://test-fhir.example.com/fhir"
        respx.get(f"{base_url}/MedicationRequest").mock(
            return_value=Response(200, json=sample_medications_fhir)
        )

        tools = FHIRTools(base_url=base_url, trace_id="test-trace")
        result = tools.get_active_medications(patient_id=1)

        assert result.success is True
        assert result.data is not None
        assert result.data["resourceType"] == "Bundle"
        tools.close()

    @respx.mock
    def test_get_recent_labs_success(self, sample_labs_fhir):
        """Test successful labs retrieval."""
        base_url = "http://test-fhir.example.com/fhir"
        respx.get(f"{base_url}/Observation").mock(return_value=Response(200, json=sample_labs_fhir))

        tools = FHIRTools(base_url=base_url, trace_id="test-trace")
        result = tools.get_recent_labs(patient_id=1, days=90)

        assert result.success is True
        assert result.data is not None
        tools.close()

    @respx.mock
    def test_get_problem_list_success(self, sample_conditions_fhir):
        """Test successful problem list retrieval."""
        base_url = "http://test-fhir.example.com/fhir"
        respx.get(f"{base_url}/Condition").mock(return_value=Response(200, json=sample_conditions_fhir))

        tools = FHIRTools(base_url=base_url, trace_id="test-trace")
        result = tools.get_problem_list(patient_id=1)

        assert result.success is True
        assert result.data is not None
        tools.close()

    @respx.mock
    def test_get_last_encounter_success(self, sample_encounter_fhir):
        """Test successful encounter retrieval."""
        base_url = "http://test-fhir.example.com/fhir"
        respx.get(f"{base_url}/Encounter").mock(return_value=Response(200, json=sample_encounter_fhir))

        tools = FHIRTools(base_url=base_url, trace_id="test-trace")
        result = tools.get_last_encounter(patient_id=1)

        assert result.success is True
        assert result.data is not None
        tools.close()

    @respx.mock
    def test_http_error_handling(self):
        """Test HTTP 500 error handling."""
        base_url = "http://test-fhir.example.com/fhir"
        respx.get(f"{base_url}/Patient/1").mock(return_value=Response(500, text="Internal Server Error"))

        tools = FHIRTools(base_url=base_url, trace_id="test-trace")
        result = tools.get_patient(patient_id=1)

        assert result.success is False
        assert "500" in result.error
        tools.close()
