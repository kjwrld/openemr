# Clinical Co-Pilot Agent Architecture

## Executive Summary (~500 words)

[TODO: High-level architecture overview with key decisions, major considerations, and tradeoffs]

---

## Architecture Overview

### System Components

[TODO: Agent service, OpenEMR, databases, caching layer]

### Deployment Architecture

[TODO: How services are deployed - Railway, docker-compose, etc.]

---

## Agent Service Design

### Stack

- **Runtime:** TypeScript + Hono
- **LLM:** Claude Sonnet 4.7 (main agent), Claude Haiku 4.5 (verifier)
- **Database:** Postgres + pgvector
- **Cache:** Redis
- **Observability:** Langfuse (self-hosted)

### Agent Architecture

[TODO: Single agent vs multi-agent, state management, tool integration]

---

## Authorization & Access Control

### JWT Passthrough Pattern

[TODO: How agent inherits clinician's OpenEMR session permissions]

### Patient-ID Binding

[TODO: How patient_id is bound into JWT to prevent cross-patient injection]

### Zero Hardcoded Rules

[TODO: Agent has zero hardcoded authorization rules - inherits from OpenEMR ACL]

---

## Verification System

### Layer 1: Source Attribution

[TODO: Structured output schema enforcement - every claim must cite source_id]

### Layer 2: Clinical Rules Verifier

[TODO: Haiku call runs in parallel, adds warning banners but doesn't block]

---

## Audit Logging

### Append-Only Design

[TODO: Postgres table, hash-chained for tamper evidence]

### What Gets Logged

[TODO: Who/what patient/what data/when/why for every FHIR call]

### Role-Based DB Permissions

[TODO: INSERT only for app role, no UPDATE/DELETE]

### Separation from Observability

[TODO: Audit log vs Langfuse traces]

---

## Performance Optimization

### Pre-warming Patient Context

[TODO: Schedule load → Redis cache]

### Response Streaming

[TODO: SSE for real-time response delivery]

### Parallel Tool Calls

[TODO: How concurrent FHIR queries are executed]

---

## Read vs Write Operations

### Read Operations

[TODO: Free access via FHIR API with inherited permissions]

### Write Operations

[TODO: Draft → Review → Confirm pattern, explicit clinician approval required]

### MVP Write Tools

1. `draft_visit_note`
2. `draft_followup_appointment`

---

## Integration with OpenEMR

### FHIR R4 Endpoints

[TODO: Which endpoints the agent uses, how auth works]

### OAuth2 Scopes

[TODO: What scopes are requested]

### ACL System Integration

[TODO: How OpenEMR's ACL system is respected]

---

## Data Flow

[TODO: Request flow from agent → OpenEMR → response]

---

## Failure Modes & Error Handling

### Tool Failures

[TODO: What happens when a FHIR call fails]

### Missing Patient Data

[TODO: How agent handles incomplete records]

### Unexpected Model Output

[TODO: Validation and graceful degradation]

---

## Deployment & Scaling

### Stateless Design

[TODO: Why agent service is stateless, how it enables horizontal scaling]

### Railway Deployment

[TODO: Service configuration, environment variables, networking]

---

## Known Limitations & Future Work

[TODO: What's out of scope for MVP, what needs improvement]
