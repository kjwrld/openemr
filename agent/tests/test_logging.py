"""Unit tests for logging."""

import pytest

from logging_config import hash_patient_id, generate_trace_id


@pytest.mark.unit
class TestLogging:
    """Test logging utilities."""

    def test_hash_patient_id_consistent(self):
        """Test that hashing the same ID produces same hash."""
        patient_id = 123
        hash1 = hash_patient_id(patient_id)
        hash2 = hash_patient_id(patient_id)

        assert hash1 == hash2
        assert hash1.startswith("sha256:")

    def test_hash_patient_id_different(self):
        """Test that different IDs produce different hashes."""
        hash1 = hash_patient_id(123)
        hash2 = hash_patient_id(456)

        assert hash1 != hash2

    def test_hash_patient_id_string(self):
        """Test hashing patient ID as string."""
        hash1 = hash_patient_id("123")
        hash2 = hash_patient_id(123)

        # String "123" and int 123 should hash the same
        assert hash1 == hash2

    def test_generate_trace_id_unique(self):
        """Test that trace IDs are unique."""
        trace1 = generate_trace_id()
        trace2 = generate_trace_id()

        assert trace1 != trace2
        # Should be valid UUIDs (36 chars with dashes)
        assert len(trace1) == 36
        assert len(trace2) == 36
