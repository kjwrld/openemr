# Clinical Co-Pilot Architecture

## Executive Summary

This agent sits between clinicians and OpenEMR's FHIR R4 API, executing structured workflows instead of free-form conversation. The core insight: clinical decision support requires **bounded, verifiable operations**, not open-ended chat.

**Two-envelope safety model:**
- **Ingress validation**: Parse user intent into typed workflows with explicit FHIR call limits (max 10/request)
- **Egress verification**: 4-pass verification stack buffers responses, validates before streaming

**Authorization without hardcoded rules:** JWT passthrough from SMART on FHIR OAuth means the agent inherits user permissions—if the clinician can't read a resource, neither can the agent. Zero authorization logic in our code.

**Pre-warm pipeline:** FAQ pre-generation runs async after encounters close, caching common queries (e.g., "summarize today's visits") with 24h TTL. Suggestion chips surface these cached responses, avoiding cold-start latency for routine questions.

**Workflow architecture:** Router classifies intent → DAG executor runs typed nodes (read encounter, check vitals, draft summary) → 4-pass verification → stream response. Not conversational; more like GraphQL for clinical data with LLM-generated queries.

---

## Key Architectural Decisions

### 1. Router → DAG Workflow Pattern

**Decision:** Structured workflow execution instead of conversational agent.

**Why:** Clinical tasks decompose naturally into directed acyclic graphs:
- "Summarize Mr. Smith's visit" → [Read Encounter] → [Read Vitals] → [Read Medications] → [Generate Summary]
- "Check abnormal labs" → [Read Observations, filter LOINC] → [Compare reference ranges] → [Draft alert]

Each node has explicit FHIR calls, success/failure modes, and retry logic. The LLM classifies intent and generates the DAG; execution is deterministic.

**Tradeoff:** Loses flexibility of open conversation but gains auditability, performance (parallel node execution), and verification (we know exactly what data informed each output).

### 2. 4-Pass Verification Stack

**Decision:** Buffer full response, run 4 verification passes, then stream.

**Passes:**
1. **Citation grounding**: Every claim must reference a FHIR resource (Encounter ID, Observation ID, etc.)
2. **LLM-as-judge** (Haiku): Check for hallucination, tone appropriateness, missing context
3. **Deterministic domain rules**: Vitals out of range → flag; medication contraindications → block; age/gender mismatches → error
4. **Cross-source consistency**: If two FHIR resources conflict (e.g., duplicate active medications), surface the discrepancy explicitly

**Why:** Healthcare AI needs defense-in-depth. LLMs alone miss edge cases (Haiku catches most hallucinations but not domain-specific errors like dangerous drug interactions). Deterministic rules catch those. Cross-source consistency handles EHR data quality issues.

**Tradeoff:** Adds 200-400ms latency (buffering + verification) vs streaming immediately. Worth it—silent failures in clinical contexts are unacceptable.

### 3. Pre-Warm Pipeline with FAQ Pre-Generation

**Decision:** After encounter state changes (closed, updated), async worker generates answers to common queries and caches them (24h TTL).

**Common queries:**
- "Summarize today's visits"
- "Any abnormal vitals?"
- "Pending orders for [patient]"

**Why:** Cold-start latency (LLM call + FHIR fetches + verification) averages 2-3 seconds. Pre-warming common queries drops this to <200ms for cache hits. Clinicians asking predictable questions get instant responses.

**Implementation:**
- Redis cache stores FHIR URLs and metadata (not PHI)
- Suggestion chips in UI surface cached queries
- Cache invalidation on encounter updates (vitals added, meds changed)

**Tradeoff:** Increases backend cost (async FAQ generation) but massively improves UX for routine queries. 24h TTL balances freshness and cost.

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
- TypeScript + Hono (lightweight, edge-deployable)
- Claude Sonnet 4.8 (intent classification, DAG generation)
- Claude Opus 4.7 (complex summaries, multi-patient workflows)
- Claude Haiku 4.5 (LLM-as-judge verification)

**Data Layer:**
- Postgres (audit log with hash chaining for tamper detection)
- Redis (cache metadata, max 24h TTL, no PHI storage)

**EHR Integration:**
- SMART on FHIR (OAuth + PKCE, no custom auth)
- JWT passthrough for authorization (zero hardcoded permission logic)

**Observability:**
- Langfuse Cloud HIPAA region (request tracing, LLM logs)
- All FHIR calls logged to Postgres audit table

---

## Verification Strategy Deep Dive

**Why 4 passes instead of 1?**

Each pass catches different error classes:

1. **Citation grounding** (deterministic): Catches "make up a plausible answer" hallucinations
2. **LLM-as-judge** (statistical): Catches tone issues, incomplete reasoning, missing disclaimers
3. **Deterministic domain rules** (coded logic): Catches clinical errors LLMs can't reliably detect (drug interactions, abnormal vitals)
4. **Cross-source consistency** (heuristic): Catches EHR data quality issues (duplicate records, conflicting entries)

Running all 4 in sequence means failures early in the stack (missing citations) short-circuit—no need to run expensive LLM-as-judge if basic validation fails.

**Buffer-Verify-Stream pattern:**
```
User query → Router → DAG execution → Buffer full response →
  Pass 1 (citations) → Pass 2 (LLM judge) → Pass 3 (domain rules) → Pass 4 (consistency) →
  Stream to user
```

All verification completes before the user sees the first token. Latency cost is acceptable (200-400ms) given the risk reduction.

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
- Langfuse trace logs: HIPAA-compliant region, BAA in place

**What's out of scope (no PHI storage):**
- Redis cache: stores FHIR URLs and metadata only (e.g., "Encounter/123", "last updated: 2026-04-28T10:00Z")
- Agent service memory: stateless, no session storage
- LLM provider: Claude (Anthropic has BAA, but we still avoid sending unnecessary PHI—use resource IDs in prompts, not full patient narratives)

**Why this matters:** Smaller HIPAA surface area = less compliance overhead, lower breach risk, simpler audit trail.

---

## Latency Constraints

**Target latency:**
- Cached queries (FAQ pre-gen): <200ms
- Cold queries (FHIR fetch + LLM + verification): <3s for p95
- Write confirmations: <1s for draft generation

**How we hit these targets:**
1. Parallel DAG node execution (fetch vitals + meds + labs concurrently)
2. Pre-warm pipeline for common queries
3. Haiku for verification (50-100ms vs Sonnet's 200-400ms)
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
