"""Unit tests for verification."""

import pytest

from verification import extract_citations, verify_response


@pytest.mark.unit
class TestVerification:
    """Test verification functions."""

    def test_extract_citations_single(self):
        """Test extracting a single citation."""
        text = "Patient has diabetes [source: Condition/c123]."
        citations = extract_citations(text)

        assert len(citations) == 1
        assert citations[0]["source_id"] == "Condition/c123"

    def test_extract_citations_multiple(self):
        """Test extracting multiple citations."""
        text = "BP is 145/90 [source: Observation/v789] and A1C is 6.8% [source: Observation/o123]."
        citations = extract_citations(text)

        assert len(citations) == 2
        assert citations[0]["source_id"] == "Observation/v789"
        assert citations[1]["source_id"] == "Observation/o123"

    def test_extract_citations_none(self):
        """Test text with no citations."""
        text = "This is a response with no citations."
        citations = extract_citations(text)

        assert len(citations) == 0

    def test_verify_response_with_citations(self):
        """Test verification passes with citations."""
        response = "BP is 145/90 [source: Observation/v789]."
        tool_calls = [{"name": "get_vitals", "success": True, "source_id": "Observation/v789"}]

        result = verify_response(response, tool_calls)

        assert result.passed is True
        assert len(result.citations) == 1

    def test_verify_response_no_citations(self):
        """Test verification flags response without citations."""
        response = "This is a long response with specific claims about BP 145/90 but no citations."
        tool_calls = []

        result = verify_response(response, tool_calls)

        # Should fail since it's a substantial response with no citations
        assert result.passed is False
        assert len(result.warnings) > 0

    def test_verify_response_no_data_acceptable(self):
        """Test that 'no data' responses pass without citations."""
        response = "No recent lab results available for this patient."
        tool_calls = []

        result = verify_response(response, tool_calls)

        # Should pass since it explicitly says no data
        assert result.passed is True

    def test_verify_response_error_acceptable(self):
        """Test that error responses pass without citations."""
        response = "Error: Unable to retrieve patient data."
        tool_calls = []

        result = verify_response(response, tool_calls)

        # Should pass since it's an error message
        assert result.passed is True

    def test_uncited_claim_warning(self):
        """Test that specific values without nearby citations generate warnings."""
        response = "Patient's BP is 145/90 and this claim is far from any citation."
        tool_calls = []

        result = verify_response(response, tool_calls)

        # Should generate warning about uncited BP reading
        assert len(result.warnings) > 0
