"""FHIR R4 tools for accessing OpenEMR patient data."""

import time
from typing import Any, Union

import httpx
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings

from logging_config import logger, generate_trace_id


class Settings(BaseSettings):
    """FHIR API settings."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    openemr_fhir_base_url: str = "http://localhost:8300/apis/default/fhir"
    fhir_timeout: int = 10  # seconds


settings = Settings()


class FHIRToolResult(BaseModel):
    """Standard tool result with source citation."""

    data: Union[dict[str, Any], list[dict[str, Any]], None]
    source_id: Union[str, None]
    source_url: str
    success: bool
    error: Union[str, None] = None


class FHIRTools:
    """FHIR R4 tools for patient data retrieval."""

    def __init__(self, base_url: Union[str, None] = None, trace_id: Union[str, None] = None):
        self.base_url = base_url or settings.openemr_fhir_base_url
        self.trace_id = trace_id or generate_trace_id()
        self.client = httpx.Client(timeout=settings.fhir_timeout)

    def _call_fhir(self, endpoint: str, tool_name: str) -> FHIRToolResult:
        """Internal helper to call FHIR API with error handling and logging."""
        url = f"{self.base_url}/{endpoint}"
        start_time = time.time()

        try:
            response = self.client.get(url)
            duration_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 404:
                logger.log_tool_call(
                    self.trace_id, tool_name, duration_ms, success=False, error="404 Not Found"
                )
                return FHIRToolResult(
                    data=None,
                    source_id=None,
                    source_url=url,
                    success=False,
                    error="Resource not found",
                )

            response.raise_for_status()
            data = response.json()

            logger.log_tool_call(self.trace_id, tool_name, duration_ms, success=True)

            # Extract resource ID from response
            source_id = None
            if isinstance(data, dict):
                if "id" in data:
                    source_id = f"{data.get('resourceType', 'Unknown')}/{data['id']}"
                elif "entry" in data and len(data["entry"]) > 0:
                    first_entry = data["entry"][0].get("resource", {})
                    if "id" in first_entry:
                        source_id = f"{first_entry.get('resourceType', 'Unknown')}/{first_entry['id']}"

            return FHIRToolResult(
                data=data,
                source_id=source_id,
                source_url=url,
                success=True,
            )

        except httpx.TimeoutException:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.log_tool_call(self.trace_id, tool_name, duration_ms, success=False, error="Timeout")
            return FHIRToolResult(
                data=None,
                source_id=None,
                source_url=url,
                success=False,
                error="FHIR API timeout",
            )

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.log_tool_call(
                self.trace_id, tool_name, duration_ms, success=False, error=f"HTTP {e.response.status_code}"
            )
            return FHIRToolResult(
                data=None,
                source_id=None,
                source_url=url,
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text[:100]}",
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.log_tool_call(
                self.trace_id, tool_name, duration_ms, success=False, error=str(e)
            )
            return FHIRToolResult(
                data=None,
                source_id=None,
                source_url=url,
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

    def get_patient(self, patient_id: int) -> FHIRToolResult:
        """Get patient demographics."""
        return self._call_fhir(f"Patient/{patient_id}", "get_patient")

    def get_recent_vitals(self, patient_id: int, count: int = 3) -> FHIRToolResult:
        """Get recent vital signs (BP, HR, temp, weight)."""
        endpoint = f"Observation?patient={patient_id}&category=vital-signs&_sort=-date&_count={count}"
        return self._call_fhir(endpoint, "get_recent_vitals")

    def get_active_medications(self, patient_id: int) -> FHIRToolResult:
        """Get active medication list."""
        endpoint = f"MedicationRequest?patient={patient_id}&status=active"
        return self._call_fhir(endpoint, "get_active_medications")

    def get_recent_labs(self, patient_id: int, days: int = 90) -> FHIRToolResult:
        """Get recent lab results (last N days)."""
        # Note: FHIR date filtering would use _lastUpdated or date parameter
        # For simplicity, we'll fetch recent labs and let the LLM filter by date
        endpoint = f"Observation?patient={patient_id}&category=laboratory&_sort=-date&_count=20"
        return self._call_fhir(endpoint, "get_recent_labs")

    def get_problem_list(self, patient_id: int) -> FHIRToolResult:
        """Get active problem list (conditions)."""
        endpoint = f"Condition?patient={patient_id}"
        return self._call_fhir(endpoint, "get_problem_list")

    def get_last_encounter(self, patient_id: int) -> FHIRToolResult:
        """Get most recent clinical encounter."""
        endpoint = f"Encounter?patient={patient_id}&_sort=-date&_count=1"
        return self._call_fhir(endpoint, "get_last_encounter")

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
