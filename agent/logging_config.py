"""Structured JSON logging for the Clinical Co-Pilot agent."""

import hashlib
import hmac
import json
import logging
import sys
import time
import uuid
from typing import Any, Union

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-key-change-in-production"
    log_level: str = "INFO"


settings = Settings()


def hash_patient_id(patient_id: Union[int, str]) -> str:
    """Hash patient ID using HMAC-SHA256 to protect PHI in logs."""
    patient_str = str(patient_id).encode()
    secret = settings.secret_key.encode()
    hashed = hmac.new(secret, patient_str, hashlib.sha256).hexdigest()
    return f"sha256:{hashed[:16]}"  # Truncate for readability


class StructuredLogger:
    """Structured logger that outputs JSON to stdout."""

    def __init__(self):
        self.logger = logging.getLogger("clinical_copilot")
        self.logger.setLevel(getattr(logging, settings.log_level.upper()))

        # JSON handler for stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

    def log_request(
        self,
        trace_id: str,
        patient_id: Union[int, str],
        message: str,
        tool_calls: Union[list[dict[str, Any]], None] = None,
        tokens_in: Union[int, None] = None,
        tokens_out: Union[int, None] = None,
        cost_usd: Union[float, None] = None,
        total_latency_ms: Union[int, None] = None,
        error: Union[str, None] = None,
    ) -> None:
        """Log a request with structured data."""
        log_entry = {
            "timestamp": time.time(),
            "trace_id": trace_id,
            "patient_id_hash": hash_patient_id(patient_id),
            "message_length": len(message),
            "tool_calls": tool_calls or [],
            "tokens": {
                "input": tokens_in,
                "output": tokens_out,
            },
            "cost_usd": cost_usd,
            "latency_ms": total_latency_ms,
            "error": error,
        }
        self.logger.info(json.dumps(log_entry))

    def log_tool_call(
        self,
        trace_id: str,
        tool_name: str,
        duration_ms: int,
        success: bool,
        error: Union[str, None] = None,
    ) -> None:
        """Log an individual tool call."""
        log_entry = {
            "timestamp": time.time(),
            "trace_id": trace_id,
            "event": "tool_call",
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
        }
        self.logger.info(json.dumps(log_entry))


def generate_trace_id() -> str:
    """Generate a unique trace ID for request tracking."""
    return str(uuid.uuid4())


# Global logger instance
logger = StructuredLogger()
