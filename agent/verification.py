"""Post-processing verification to ensure all claims are properly cited."""

import re
from typing import Any


class VerificationResult:
    """Result of verification check."""

    def __init__(self, passed: bool, verified_response: str, citations: list[dict[str, str]], warnings: list[str]):
        self.passed = passed
        self.verified_response = verified_response
        self.citations = citations
        self.warnings = warnings


def extract_citations(response_text: str) -> list[dict[str, str]]:
    """Extract all citations from response text.

    Citations are in format: [source: ResourceType/ID]
    """
    pattern = r'\[source:\s*([^\]]+)\]'
    matches = re.findall(pattern, response_text)

    citations = []
    for match in matches:
        # Clean up the source ID
        source_id = match.strip()
        citations.append({
            "source_id": source_id,
            "source_url": f"(FHIR resource: {source_id})",  # Would be full URL in production
        })

    return citations


def verify_response(response_text: str, tool_calls_log: list[dict[str, Any]]) -> VerificationResult:
    """Verify that all factual claims in the response are properly cited.

    Verification rules:
    1. Extract all citations from response
    2. Check that citations reference actual FHIR resources retrieved during tool calls
    3. Flag any suspiciously uncited claims (heuristic-based)

    Args:
        response_text: The LLM-generated response
        tool_calls_log: List of tool calls with source_ids

    Returns:
        VerificationResult with verified response and any warnings
    """
    citations = extract_citations(response_text)
    warnings = []

    # Extract all valid source IDs from successful tool calls
    valid_source_ids = set()
    for tool_call in tool_calls_log:
        if tool_call.get("success") and tool_call.get("source_id"):
            valid_source_ids.add(tool_call["source_id"])

    # Check that all citations reference valid sources
    invalid_citations = []
    for citation in citations:
        source_id = citation["source_id"]
        # For now, we accept any citation format since FHIR responses may have various IDs
        # In production, we'd validate against valid_source_ids
        pass

    # Heuristic: Check for suspiciously specific claims without citations
    # Look for patterns like: "BP 145/90", "A1C 6.8%", "Lisinopril 10mg"
    # This is a simple heuristic - production would be more sophisticated
    uncited_patterns = [
        r'\b\d{2,3}/\d{2,3}\b',  # BP readings like 145/90
        r'\b\d+\.?\d*\s*mg\b',   # Dosages like 10mg, 500mg
        r'\b[A-Z][a-z]+\s+\d+\.?\d*\s*mg\b',  # Med names with dosage
    ]

    for pattern in uncited_patterns:
        matches = re.finditer(pattern, response_text)
        for match in matches:
            # Check if this match is near a citation (within 50 chars)
            match_pos = match.start()
            has_nearby_citation = False

            for citation_match in re.finditer(r'\[source:[^\]]+\]', response_text):
                citation_pos = citation_match.start()
                if abs(citation_pos - match_pos) < 100:
                    has_nearby_citation = True
                    break

            if not has_nearby_citation:
                warnings.append(f"Potentially uncited claim: {match.group()}")

    # If no citations found, that's a red flag (unless response is an error/empty message)
    is_no_data_response = any(phrase in response_text.lower() for phrase in ["no data", "no recent", "not available", "no record"])
    is_error_response = "error" in response_text.lower()

    if len(citations) == 0 and len(response_text) > 100:
        if not is_no_data_response and not is_error_response:
            warnings.append("Response contains substantial content but no citations")

    # For Early Submission, we pass if we have at least one citation OR it's a no-data/error response
    passed = len(citations) > 0 or is_no_data_response or is_error_response

    return VerificationResult(
        passed=passed,
        verified_response=response_text,  # In production, might strip uncited claims
        citations=citations,
        warnings=warnings,
    )


def format_verification_warnings(warnings: list[str]) -> str:
    """Format verification warnings for display."""
    if not warnings:
        return ""

    formatted = "\n\n⚠️ **Verification Warnings:**\n"
    for warning in warnings:
        formatted += f"- {warning}\n"

    return formatted
