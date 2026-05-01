"""FastAPI application for Clinical Co-Pilot agent."""

import time
from typing import Any, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from llm import ClinicalAgent
from logging_config import generate_trace_id, hash_patient_id, logger
from verification import verify_response, format_verification_warnings

# Initialize FastAPI app
app = FastAPI(
    title="Clinical Co-Pilot Agent",
    description="AI agent for pre-visit patient summaries",
    version="0.1.0",
)

# CORS middleware - allow requests from chat widget
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting: 10 requests per minute per IP
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files for chat widget UI
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    """Chat endpoint request schema."""

    patient_id: int = Field(..., description="Patient ID from OpenEMR")
    message: str = Field(..., description="User message/query")
    conversation_id: Union[str, None] = Field(None, description="Optional conversation ID for multi-turn")


class CitationModel(BaseModel):
    """Citation model for response."""

    source_id: str
    source_url: str


class ChatResponse(BaseModel):
    """Chat endpoint response schema."""

    response: str
    citations: list[CitationModel]
    conversation_id: str
    trace_id: str
    latency_ms: int
    patient_id_hash: str
    warnings: list[str] = []


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    # TODO: Could add checks for FHIR API availability
    return {
        "status": "healthy",
        "service": "clinical-copilot-agent",
        "version": "0.1.0",
    }


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest) -> ChatResponse:
    """Main chat endpoint for generating pre-visit summaries.

    Rate limited to 10 requests per minute per IP.
    """
    start_time = time.time()
    trace_id = generate_trace_id()

    try:
        # Create agent
        agent = ClinicalAgent(trace_id=trace_id)

        # Generate summary using Claude + tools
        response_text, tool_calls_log, usage = agent.generate_pre_visit_summary(
            patient_id=chat_request.patient_id,
            user_message=chat_request.message,
        )

        # Verify response (check for citations)
        verification_result = verify_response(response_text, tool_calls_log)

        # Calculate costs (Anthropic pricing as of 2024)
        # Claude Sonnet 4: $3/MTok input, $15/MTok output
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost_usd = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)

        # Calculate latency
        total_latency_ms = int((time.time() - start_time) * 1000)

        # Log request
        logger.log_request(
            trace_id=trace_id,
            patient_id=chat_request.patient_id,
            message=chat_request.message,
            tool_calls=[
                {
                    "name": tc["name"],
                    "success": tc["success"],
                }
                for tc in tool_calls_log
            ],
            tokens_in=input_tokens,
            tokens_out=output_tokens,
            cost_usd=cost_usd,
            total_latency_ms=total_latency_ms,
        )

        # Format warnings if any
        warnings_text = format_verification_warnings(verification_result.warnings)
        final_response = verification_result.verified_response + warnings_text

        # Build response
        return ChatResponse(
            response=final_response,
            citations=[CitationModel(**c) for c in verification_result.citations],
            conversation_id=chat_request.conversation_id or trace_id,
            trace_id=trace_id,
            latency_ms=total_latency_ms,
            patient_id_hash=hash_patient_id(chat_request.patient_id),
            warnings=verification_result.warnings,
        )

    except Exception as e:
        # Log error
        total_latency_ms = int((time.time() - start_time) * 1000)
        logger.log_request(
            trace_id=trace_id,
            patient_id=chat_request.patient_id,
            message=chat_request.message,
            total_latency_ms=total_latency_ms,
            error=str(e),
        )

        # Return error response
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    finally:
        # Clean up agent resources
        if 'agent' in locals():
            agent.close()


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit error response."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": "Maximum 10 requests per minute. Please try again later.",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
