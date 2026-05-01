# Early Submission Build Plan — April 30, 2026

## Mission
Ship a working deployed agent with verification, observability, tests, and evals by 11:59 PM CT tonight.

## Agents Deployed

### Agent 1: Builder (Python Backend)
**Mission**: Create the agent service in `agent/` directory
**Deliverables**:
- `agent/main.py` — FastAPI app with POST /chat endpoint
- `agent/tools.py` — 6 FHIR tools (get_patient, get_vitals, get_meds, get_labs, get_problems, get_last_encounter)
- `agent/llm.py` — Anthropic SDK wrapper for Claude Sonnet 4.5
- `agent/verification.py` — Post-process citation checker
- `agent/logging_config.py` — Structured JSON logging (trace_id, patient_id_hash, tool_calls, latency, tokens, cost)
- `agent/requirements.txt` — fastapi, anthropic, httpx, pydantic, slowapi, python-dotenv
- `agent/Dockerfile` — Python 3.11 slim
- `agent/.env.example` — Template env vars

**Constraints**:
- FHIR R4 API only (no direct DB access)
- Claude Sonnet 4.5 for tool use
- Every response must include citations
- Hash patient_id before logging (HMAC-SHA256)
- Rate limit: 10 req/min per IP

### Agent 2: Testing & Eval Framework
**Mission**: Create unit tests + integration tests + eval suite
**Deliverables**:

**Unit Tests (`agent/tests/`):**
- `test_tools.py` — Test each FHIR tool with mocked httpx responses
- `test_verification.py` — Test citation checker with valid/invalid responses
- `test_logging.py` — Test patient_id hashing, structured log format
- `pytest.ini` — Pytest config
- Add to `requirements.txt`: pytest, pytest-asyncio, pytest-httpx

**Integration Tests (`agent/tests/integration/`):**
- `test_chat_endpoint.py` — Test POST /chat with TestClient
- `test_rate_limiting.py` — Test slowapi rate limiter
- `test_error_handling.py` — Test missing patient, FHIR timeout, malformed request

**Eval Framework (`agent/evals/`):**
- `cases.json` — 7 test cases:
  - 2 happy path (valid patient with full chart data)
  - 2 missing data (patient with no labs, patient with empty problem list)
  - 2 auth boundary (nonexistent patient_id, patient_id as string attack)
  - 1 hallucination trap (ask about medication patient is NOT on)
- `run_evals.py` — Execute cases against /chat, print pass/fail table
- `requirements-dev.txt` — pytest, respx (for mocking FHIR)

**Pass criteria**:
- Unit tests: 100% of tools return expected structure
- Integration: /chat returns 200 with citations
- Evals: Structural (response includes citation), substring checks, missing data handling

### Agent 3: Research (OpenEMR Schema)
**Mission**: Explore deployed OpenEMR to understand FHIR endpoints and sample data
**Deliverables**:
- Document FHIR base URL (should be Railway deployment URL + `/apis/default/fhir`)
- Test FHIR metadata endpoint: `GET /metadata`
- Find sample patient IDs in the deployed instance
- Test each of the 6 FHIR endpoints we're using with a real patient
- Document response shapes in `agent/FHIR_RESPONSES.md`
- Create sample FHIR response fixtures for unit tests

**Tools**: curl, httpx (Python), Railway logs

### Agent 4: Deployment
**Mission**: Deploy agent service to Railway
**Deliverables**:
- `agent/railway.json` or `railway.toml` — Service config
- Railway service created (same project as OpenEMR, separate service)
- Environment variables set: ANTHROPIC_API_KEY, OPENEMR_FHIR_BASE_URL
- Healthcheck endpoint: GET /health
- Deployed URL verified (curl test against /chat)
- CI/CD: Run pytest before deploy (Railway build command)

**Rate limiting**: slowapi with 10 req/min

## Test Coverage Requirements

### Unit Tests
- [ ] All 6 FHIR tools return typed responses
- [ ] Citation checker rejects responses without sources
- [ ] Citation checker accepts valid responses with source_id
- [ ] Patient ID hashing produces consistent SHA256 output
- [ ] Structured logs include all required fields

### Integration Tests
- [ ] POST /chat returns 200 with valid patient_id
- [ ] POST /chat returns 404 with invalid patient_id
- [ ] Rate limiter blocks 11th request in 1 minute
- [ ] FHIR timeout returns graceful error (not 500)

### Eval Suite
- [ ] Happy path: generates summary with 3+ citations
- [ ] Missing data: surfaces "no labs found" vs. hallucinating
- [ ] Auth boundary: rejects nonexistent patient
- [ ] Hallucination trap: says "patient not on X medication"

**Target**: 90%+ pass rate on evals, 100% pass on unit/integration tests

## Success Criteria (Tonight)

- [ ] `pytest agent/tests/` passes (all unit + integration tests green)
- [ ] `/chat` endpoint responds in <6 seconds
- [ ] Every claim includes a citation (source FHIR resource)
- [ ] Eval suite runs and prints pass/fail (target: 6/7 pass)
- [ ] Deployed agent URL is publicly accessible
- [ ] curl demo works:
  ```bash
  curl -X POST https://agent.up.railway.app/chat \
    -H "Content-Type: application/json" \
    -d '{"patient_id": 1, "message": "Give me a pre-visit summary"}'
  ```

## Demo Output (for video)

```json
{
  "response": "**John Doe, 62M - Annual Physical**\n\n**Changed since last visit (3 months ago):**\n- BP trending upward: 138/84 → 142/88 → 145/90 [source: Observation/v789]\n- Started Lisinopril 10mg 2 weeks ago [source: MedicationRequest/m456]\n- A1C stable at 6.8%, below target <7.0 [source: Observation/o123]\n\n**Red flags:**\n⚠️ BP remains elevated despite new medication\n\n**Context for today:**\nLast visit discussed lifestyle modifications. Patient scheduled for 2-week BP recheck but didn't follow up.",
  "citations": [
    {"source_id": "Observation/v789", "claim": "BP 145/90"},
    {"source_id": "MedicationRequest/m456", "claim": "Lisinopril 10mg"},
    {"source_id": "Observation/o123", "claim": "A1C 6.8%"}
  ],
  "trace_id": "abc123-def456",
  "patient_id_hash": "sha256:e3b0c44...",
  "latency_ms": 4200
}
```

## Test Commands

```bash
# Run all tests
pytest agent/tests/ -v

# Run unit tests only
pytest agent/tests/test_*.py -v

# Run integration tests
pytest agent/tests/integration/ -v

# Run evals
python agent/evals/run_evals.py

# Run tests with coverage
pytest --cov=agent --cov-report=term-missing
```

## ⚡ SCOPE CHANGE: UI Required Tonight

**NEW REQUIREMENT:** Build embedded chat widget in OpenEMR interface for demo video.

### UI Components to Build Tonight:

1. **Simple Chat Widget (`public/chat-widget.html`)**
   - Standalone HTML page with embedded JavaScript
   - Can be iframe'd into OpenEMR or opened separately
   - Chat interface with message history
   - Display citations inline
   - Patient ID input field

2. **Minimal Integration**
   - No OpenEMR session auth (use hardcoded patient_id for demo)
   - Widget calls agent service directly
   - For demo video: show side-by-side (OpenEMR patient screen + chat widget)

### Deferred to Final

- Full OpenEMR session integration with JWT
- Embedded widget card in patient summary page
- 3 more use cases
- Clinical rules verifier
- Langfuse observability
- Postgres audit log
- Multi-turn conversation state

## Timeline (UPDATED)

- **Now - 6:00 PM**: Build chat widget UI
- **6:00 PM - 7:00 PM**: Integration testing, verify widget works
- **7:00 PM - 8:00 PM**: Deploy to Railway (both agent + serve widget)
- **8:00 PM - 9:00 PM**: Run evals, test end-to-end
- **9:00 PM - 10:30 PM**: Record demo video (show widget + OpenEMR side-by-side)
- **10:30 PM - 11:59 PM**: Buffer for issues
