"""Anthropic Claude integration for clinical synthesis."""

import json
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings

from tools import FHIRTools, FHIRToolResult


class Settings(BaseSettings):
    """LLM settings."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-20250514"


settings = Settings()


class Citation(BaseModel):
    """A single citation linking a claim to a source."""

    claim: str
    source_id: str
    source_url: str


class AgentResponse(BaseModel):
    """Structured agent response with citations."""

    summary: str
    citations: list[Citation]
    uncertainty_flags: list[str] = []


SYSTEM_PROMPT = """You are a Clinical Co-Pilot for a primary care physician preparing for patient visits.

Your role:
- Generate concise pre-visit summaries using ONLY the provided patient data
- Highlight what's changed since the last visit
- Flag abnormal values or red flags
- Every factual claim MUST cite a source (FHIR resource ID)

Critical rules:
1. NEVER fabricate data. If information is missing, say "No data available for X"
2. EVERY claim must include [source: ResourceType/ID] citation
3. If you find no data from a tool call, state that explicitly
4. Use clinical terminology but keep it concise (4-6 sentences max)
5. Format as markdown with clear sections

Example output:
**John Doe, 62M - Annual Physical**

**Changed since last visit:**
- BP trending upward: 138/84 → 145/90 [source: Observation/v789]
- Started Lisinopril 10mg [source: MedicationRequest/m456]

**Red flags:**
⚠️ BP remains elevated despite medication

If data is missing, say:
"No recent lab results available in the chart."
"""


class ClinicalAgent:
    """Claude-powered clinical agent with tool use."""

    def __init__(self, trace_id: str):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.trace_id = trace_id
        self.tools = FHIRTools(trace_id=trace_id)

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> FHIRToolResult:
        """Execute a FHIR tool by name."""
        patient_id = tool_input.get("patient_id")

        if tool_name == "get_patient":
            return self.tools.get_patient(patient_id)
        elif tool_name == "get_recent_vitals":
            count = tool_input.get("count", 3)
            return self.tools.get_recent_vitals(patient_id, count)
        elif tool_name == "get_active_medications":
            return self.tools.get_active_medications(patient_id)
        elif tool_name == "get_recent_labs":
            days = tool_input.get("days", 90)
            return self.tools.get_recent_labs(patient_id, days)
        elif tool_name == "get_problem_list":
            return self.tools.get_problem_list(patient_id)
        elif tool_name == "get_last_encounter":
            return self.tools.get_last_encounter(patient_id)
        else:
            return FHIRToolResult(
                data=None,
                source_id=None,
                source_url="",
                success=False,
                error=f"Unknown tool: {tool_name}",
            )

    def generate_pre_visit_summary(self, patient_id: int, user_message: str) -> tuple[str, list[dict], dict]:
        """Generate pre-visit summary using Claude with tool use.

        Returns:
            tuple: (response_text, tool_calls_log, usage_stats)
        """
        # Define available tools for Claude
        tools = [
            {
                "name": "get_patient",
                "description": "Get patient demographics (name, age, DOB, gender)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "integer", "description": "Patient ID"},
                    },
                    "required": ["patient_id"],
                },
            },
            {
                "name": "get_recent_vitals",
                "description": "Get recent vital signs (BP, HR, temp, weight)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "integer", "description": "Patient ID"},
                        "count": {"type": "integer", "description": "Number of recent vitals to fetch", "default": 3},
                    },
                    "required": ["patient_id"],
                },
            },
            {
                "name": "get_active_medications",
                "description": "Get current active medications",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "integer", "description": "Patient ID"},
                    },
                    "required": ["patient_id"],
                },
            },
            {
                "name": "get_recent_labs",
                "description": "Get recent laboratory results",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "integer", "description": "Patient ID"},
                        "days": {"type": "integer", "description": "Number of days to look back", "default": 90},
                    },
                    "required": ["patient_id"],
                },
            },
            {
                "name": "get_problem_list",
                "description": "Get active problem list (conditions/diagnoses)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "integer", "description": "Patient ID"},
                    },
                    "required": ["patient_id"],
                },
            },
            {
                "name": "get_last_encounter",
                "description": "Get most recent clinical encounter/visit",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "integer", "description": "Patient ID"},
                    },
                    "required": ["patient_id"],
                },
            },
        ]

        messages = [
            {
                "role": "user",
                "content": f"Patient ID: {patient_id}\n\nRequest: {user_message}\n\nGenerate a pre-visit summary for this patient.",
            }
        ]

        tool_calls_log = []
        max_iterations = 10  # Prevent infinite loops

        for iteration in range(max_iterations):
            response = self.client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            )

            # Check if we have a final text response
            if response.stop_reason == "end_turn":
                # Extract text from content blocks
                text_parts = [block.text for block in response.content if hasattr(block, "text")]
                final_text = "\n".join(text_parts)

                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }

                return final_text, tool_calls_log, usage

            # Handle tool use
            if response.stop_reason == "tool_use":
                # Add assistant response to conversation
                messages.append({"role": "assistant", "content": response.content})

                # Execute all tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        # Execute tool
                        result = self._execute_tool(tool_name, tool_input)

                        # Log tool call
                        tool_calls_log.append({
                            "name": tool_name,
                            "input": tool_input,
                            "success": result.success,
                            "source_id": result.source_id,
                        })

                        # Format result for Claude
                        if result.success and result.data:
                            # Truncate large responses
                            data_str = json.dumps(result.data)
                            if len(data_str) > 5000:
                                data_str = data_str[:5000] + "... [truncated]"

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Source: {result.source_id}\n\n{data_str}",
                            })
                        else:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Error: {result.error}",
                                "is_error": True,
                            })

                # Add tool results to conversation
                messages.append({"role": "user", "content": tool_results})
            else:
                # Unexpected stop reason
                break

        # If we hit max iterations or unexpected stop
        return "Error: Unable to generate summary", tool_calls_log, {}

    def close(self):
        """Clean up resources."""
        self.tools.close()
