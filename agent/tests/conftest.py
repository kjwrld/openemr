"""Shared pytest fixtures."""

import json
import pytest


@pytest.fixture
def sample_patient_fhir():
    """Sample FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": "1",
        "name": [{"family": "Doe", "given": ["John"]}],
        "gender": "male",
        "birthDate": "1964-01-15",
    }


@pytest.fixture
def sample_vitals_fhir():
    """Sample FHIR Observation (vitals) bundle."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "v789",
                    "status": "final",
                    "category": [{"coding": [{"code": "vital-signs"}]}],
                    "code": {"coding": [{"code": "85354-9", "display": "Blood pressure"}]},
                    "valueQuantity": {"value": 145, "unit": "mmHg"},
                    "effectiveDateTime": "2026-04-15",
                }
            }
        ],
    }


@pytest.fixture
def sample_medications_fhir():
    """Sample FHIR MedicationRequest bundle."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": "m456",
                    "status": "active",
                    "medicationCodeableConcept": {
                        "coding": [{"display": "Lisinopril 10mg"}]
                    },
                    "dosageInstruction": [{"text": "10mg once daily"}],
                }
            }
        ],
    }


@pytest.fixture
def sample_labs_fhir():
    """Sample FHIR Observation (labs) bundle."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "o123",
                    "status": "final",
                    "category": [{"coding": [{"code": "laboratory"}]}],
                    "code": {"coding": [{"code": "4548-4", "display": "A1C"}]},
                    "valueQuantity": {"value": 6.8, "unit": "%"},
                    "effectiveDateTime": "2026-03-20",
                }
            }
        ],
    }


@pytest.fixture
def sample_conditions_fhir():
    """Sample FHIR Condition bundle."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "c123",
                    "code": {"coding": [{"code": "E11", "display": "Type 2 Diabetes"}]},
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                }
            }
        ],
    }


@pytest.fixture
def sample_encounter_fhir():
    """Sample FHIR Encounter bundle."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "e999",
                    "status": "finished",
                    "class": {"code": "AMB"},
                    "period": {"start": "2026-01-15", "end": "2026-01-15"},
                }
            }
        ],
    }
