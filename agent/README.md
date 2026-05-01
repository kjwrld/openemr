# Clinical Co-Pilot Agent

AI agent for generating pre-visit patient summaries using Claude Sonnet 4.5 and OpenEMR's FHIR R4 API.

## Quick Start (Local Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Copy .env.example to .env and fill in values
cp .env.example .env

# Run the server
uvicorn main:app --reload --port 8000
```

## API Endpoints

### POST /chat

Generate a pre-visit summary for a patient.

**Request:**
```json
{
  "patient_id": 1,
  "message": "Give me a pre-visit summary",
  "conversation_id": null
}
```

**Response:**
```json
{
  "response": "**John Doe, 62M - Annual Physical**\n\n**Changed since last visit:**\n- BP trending upward [source: Observation/v789]...",
  "citations": [
    {
      "source_id": "Observation/v789",
      "source_url": "(FHIR resource: Observation/v789)"
    }
  ],
  "conversation_id": "abc-123",
  "trace_id": "def-456",
  "latency_ms": 4200,
  "patient_id_hash": "sha256:e3b0c44...",
  "warnings": []
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "clinical-copilot-agent",
  "version": "0.1.0"
}
```

## Architecture

- **FastAPI**: Web framework with async support
- **Anthropic SDK**: Claude Sonnet 4.5 for synthesis
- **FHIR R4 Tools**: 6 tools for patient data retrieval
- **Verification**: Post-process citation checking
- **Observability**: Structured JSON logs to stdout

## Rate Limiting

- 10 requests per minute per IP address
- 429 status code when exceeded

## Environment Variables

Required:
- `ANTHROPIC_API_KEY`: Anthropic API key
- `OPENEMR_FHIR_BASE_URL`: OpenEMR FHIR API base URL
- `SECRET_KEY`: Secret for hashing patient IDs

Optional:
- `LOG_LEVEL`: Logging level (default: INFO)
- `PORT`: Server port (default: 8000, Railway sets this)

## Deployment (Railway)

See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment instructions.

```bash
# Quick deploy
railway up
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=agent --cov-report=term-missing

# Run evals
python evals/run_evals.py
```

## Early Submission Scope

This is the Early Submission build (single use case: pre-visit summary).

**What's included:**
- 6 FHIR tools (patient, vitals, meds, labs, problems, encounters)
- Claude Sonnet 4.5 with tool use
- Citation verification
- Structured logging
- Rate limiting
- 7 eval cases

**Deferred to Final:**
- Full JWT auth with OpenEMR session integration
- Chat widget UI
- 3 more use cases
- Clinical rules verifier
- Langfuse observability
- Postgres audit log
- Multi-turn conversation state

## License

See LICENSE in repo root.
