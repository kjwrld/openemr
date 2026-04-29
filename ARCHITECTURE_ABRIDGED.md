# Clinical Co-Pilot Architecture

## Executive Summary

This agent sits between clinicians and OpenEMR's FHIR R4 API, executing structured workflows instead of free-form conversation. The core insight: clinical decision support requires **bounded, verifiable operations**, not open-ended chat.

**Two-envelope safety model:**
- **Ingress validation**: Parse user intent into typed workflows with explicit FHIR call limits (max 10/request)
- **Egress verification**: Sonnet generates response, Haiku verifies in parallel. User sees output only after both complete.

**Authorization without hardcoded rules:** JWT passthrough from SMART on FHIR OAuth means the agent inherits user permissions—if the clinician can't read a resource, neither can the agent. Zero authorization logic in our code.

**Pre-warm pipeline:** When clinician logs in, background jobs prefetch all patients on their schedule into Redis (FHIR metadata only). Avoids 2-second cold fetch in the 90-second patient review window.

**Workflow architecture:** Router classifies intent → DAG executor runs typed nodes (read encounter, check vitals, draft summary) → Parallel: Sonnet generates response + Haiku verifies → Stream after both complete. Not conversational; more like GraphQL for clinical data with LLM-generated queries.

---

## Key Architectural Decisions

### 1. Router → DAG Workflow Pattern

**Decision:** Structured workflow execution instead of conversational agent.

**Why:** Clinical tasks decompose naturally into directed acyclic graphs:
- "Summarize Mr. Smith's visit" → [Read Encounter] → [Read Vitals] → [Read Medications] → [Generate Summary]
- "Check abnormal labs" → [Read Observations, filter LOINC] → [Compare reference ranges] → [Draft alert]

Each node has explicit FHIR calls, success/failure modes, and retry logic. The LLM classifies intent and generates the DAG; execution is deterministic.

**Tradeoff:** Loses flexibility of open conversation but gains auditability, performance (parallel node execution), and verification (we know exactly what data informed each output).

### 2. Two-Model Parallel Verification

**Decision:** Sonnet generates response, Haiku verifies in parallel. User sees output only after both complete.

**Why two models, not one checking itself:** A model checking its own work inherits the same blind spots that produced the error. Two models with different prompts catch what one won't.

**Haiku verification checks:**
- Citation grounding (every claim references a FHIR resource ID)
- Hallucination detection (contradictions, unsupported claims)
- Domain rules (drug interactions, abnormal vitals, contraindications)
- Tone appropriateness (clinical, not casual)

**Why parallel, not sequential:** Running verification in parallel means zero added latency from user's perspective. Both complete in ~1-2 seconds; streaming starts only when verification passes.

**Tradeoff:** More complex than one model, higher cost (two LLM calls), but catches errors single-model architectures miss.

### 3. Pre-Warm Patient Context on Schedule Load

**Decision:** When clinician logs in, background jobs prefetch all patients on their schedule into Redis (FHIR metadata and resource URLs only, 15-minute TTL).

**Why:** In a 90-second patient review window, even a 2-second cold FHIR fetch breaks workflow. Pre-warming patients they might see eliminates wait time for patients they actually open.

**What gets cached:**
- Patient demographics URL (`/Patient/123`)
- Vitals URL (`/Observation?patient=123&category=vital-signs`)
- Active medications URL (`/MedicationRequest?patient=123&status=active`)
- Last encounter date (for sorting recent patients first)

**Why URLs not data:** Caching FHIR resource URLs avoids storing PHI in Redis. Actual data fetched on-demand with JWT passthrough for authorization.

**Tradeoff:** Burns compute pre-warming patients the clinician might skip, but eliminates latency for patients they actually see. In clinical workflows, avoiding 2-second delays is worth the cost.

### 4. Specific Failure Mode Behaviors

**Decision:** Never fail silently. Every failure state has explicit UI behavior.

| Failure Mode | Behavior |
|--------------|----------|
| FHIR API timeout | Show partial results + "Could not load [resource]" banner |
| Verification failure | Block response, log details, show "Unable to verify safety" |
| Citation missing | Reject response, retry with stricter prompt |
| Rate limit hit | Queue request, show estimated wait time |
| OpenEMR downtime | Show degraded mode: cached data only + staleness warning |

**Why:** Clinical context requires transparency. A clinician needs to know if data is incomplete, stale, or unverified—hiding failures creates liability.

**Tradeoff:** More UI complexity (designing failure states) but essential for trust.

---

## Technology Stack

**Agent Service:**
- Python 3.11 + FastAPI (async, type-safe, healthcare library ecosystem)
- Claude Sonnet 4.6 (router, DAG generation, response synthesis)
- Claude Haiku 4.5 (parallel verification, citation checking)

**Data Layer:**
- Postgres (audit log with hash chaining for tamper detection)
- Redis (cache FHIR URLs and metadata, 15-minute TTL, no PHI storage)

**EHR Integration:**
- OpenEMR FHIR R4 API
- JWT passthrough for authorization (inherits OpenEMR ACL, zero hardcoded permission logic)

**Observability:**
- Langfuse (request tracing, redacted LLM logs)
- All FHIR calls logged to Postgres audit table

---

## Verification Strategy Deep Dive

**Why two models in parallel instead of one?**

**The problem with self-verification:** A model checking its own work inherits the same blind spots that produced the error. It will rationalize mistakes rather than catch them.

**Two-model approach:**
- **Sonnet** (generator): Produces response with structured output schema enforcing citation IDs for every claim
- **Haiku** (verifier): Different prompt, different role—checks for hallucinations, missing citations, domain rule violations

Running in parallel means both complete in ~1-2 seconds. User sees no added latency vs. single-model approach.

**Verification flow:**
```
User query → Router → DAG execution →
  ├─ Sonnet generates response (with citations)
  └─ Haiku verifies response (parallel)
       ↓
  Both complete → Stream to user
```

If Haiku flags violations (missing citation, contraindicated drug), response is blocked or warning banner added before streaming.

---

## Write Safety (Draft → Review → Confirm)

Reads are bounded (max 10 FHIR calls, rate limits). Writes require explicit confirmation:

1. Agent drafts the write operation (e.g., "Add Lisinopril 10mg to medications")
2. Verification stack validates (drug interactions, dosage in range, no contraindications)
3. UI shows diff + confirmation prompt: "Add this medication? [Confirm] [Cancel]"
4. User confirms → Agent executes FHIR PATCH with JWT passthrough

No writes happen without explicit user approval. Draft → Review → Confirm pattern prevents accidental data changes.

---

## HIPAA Scope Reduction

**What's in scope:**
- Audit log (Postgres): encrypted at rest, append-only, hash-chained
- Langfuse trace logs: redacted (resource IDs only, no PHI)

**What's out of scope (no PHI storage):**
- Redis cache: stores FHIR URLs and metadata only (e.g., "Patient/123", "last_encounter_date: 2026-04-28"), 15-minute TTL
- Agent service memory: stateless, no session storage
- LLM provider: Anthropic Claude (assumes BAA in place per project requirements; minimize PHI in prompts—use resource IDs, not full patient narratives)

**Why this matters:** Smaller HIPAA surface area = less compliance overhead, lower breach risk, simpler audit trail.

---

## Latency Constraints

**Target latency:**
- Pre-warmed patient context (FHIR URLs cached): <1s for workflow execution
- Cold queries (FHIR fetch + LLM + verification): <3s for p95
- Write confirmations: <1s for draft generation

**How we hit these targets:**
1. Pre-warm patient context on schedule load (eliminates cold FHIR fetch delay)
2. Parallel DAG node execution (fetch vitals + meds + labs concurrently)
3. Parallel verification (Sonnet + Haiku run simultaneously, not sequential)
4. Rate limit FHIR calls per request (max 10) to prevent runaway latency

**Tradeoff:** Strict FHIR call limits mean some complex queries can't be answered in one request. Acceptable—prefer bounded latency over unbounded flexibility.

---

## Why Not RAG/Vector Search?

Initial design included pgvector for semantic search over clinical notes. **Removed for MVP.**

**Why:** FHIR R4 API already provides structured access to clinical data (Encounters, Observations, Medications). RAG adds complexity (embedding model, vector DB, retrieval tuning) without clear benefit for structured EHR data.

**When we'd add it back:** If unstructured clinical notes (progress notes, discharge summaries) become primary data source. For now, FHIR resources + LLM summarization suffice.

---

## Open Questions

1. **Multi-patient workflows:** Current design scopes requests to single patient. How do we handle "show me all abnormal vitals across my panel"? (Likely: batch DAG execution with per-patient rate limits)

2. **Offline mode:** What if OpenEMR is down? Currently: show cached data + staleness warning. Should we allow limited writes (queue to execute when API recovers)?

3. **Audit log retention:** HIPAA requires 6 years. Do we archive old logs to cheaper storage, or keep in hot Postgres? (Tradeoff: query performance vs cost)

4. **LLM provider failover:** If Claude API is down, do we fall back to local model (Llama 3.3)? Or just show error? (Tradeoff: availability vs verification consistency)
