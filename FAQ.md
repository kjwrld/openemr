# FAQ — OpenEMR + Clinical Co-Pilot (AgentForge fork)

A reference document for someone joining this project. Two halves: the upstream OpenEMR EHR this fork is based on, and the agentic AI stack this fork adds.

Read order: skim Part 1 to find the upstream component you care about, read Part 2 end-to-end (it's the actual delivered work), use Part 3 as a runbook.

Authoritative companions: `/mnt/c/Users/kenhu/gautlet/openemr/AUDIT.md` (audit findings with file:line), `/mnt/c/Users/kenhu/gautlet/openemr/ARCHITECTURE.md` (forward-looking design), `/mnt/c/Users/kenhu/gautlet/openemr/progress-report.md` (what's actually built today), `/mnt/c/Users/kenhu/gautlet/openemr/USERS.md` (the target user).

---

# Part 1 — OpenEMR (upstream codebase)

> Note: this fork's working tree contains only the agent stack and the deployment surfaces (`ccdaservice/`, `docker/library/`, container builders). Descriptions of upstream component paths (`interface/`, `src/`, `library/`, etc.) are sourced from the upstream `openemr/openemr` GitHub repo and from `AUDIT.md` / `ARCHITECTURE.md`, which were written against commit `a50679f63` and carry file:line references throughout. The Railway deployment runs the full stock OpenEMR image — see `/mnt/c/Users/kenhu/gautlet/openemr/deployed-to-railway.md`.

## Top-level layout

**Q: What is in `interface/`?**

The user-facing PHP/HTML/JS that renders OpenEMR's web UI. Patient summary, schedule, encounter forms, billing screens, admin pages all live here. The patient summary screen specifically lives at `interface/patient_file/summary/demographics.php`, and that's the file `ARCHITECTURE.md §3` targets for the Co-Pilot card injection. Custom modules (third-party extensions, including this project's planned `oe-module-ai-copilot`) live under `interface/modules/custom_modules/`.

**Q: What is in `src/`?**

Modern, PSR-4-namespaced PHP (`OpenEMR\` namespace) — the post-2019 application code where new development happens. PHPStan level 10 enforces strict typing. Service classes (`PatientService`, `EncounterService`, `ConditionService`, etc.) under `src/Services/` encapsulate per-resource data access with the `BaseService` pattern. Auth, sessions, ACLs, REST/FHIR controllers, the audit logger, and the event-dispatcher integration all live in subdirectories under `src/`. `AUDIT.md §3` is explicit: new code goes here, not in `library/`.

**Q: What is in `library/`?**

Legacy procedural PHP and shared helpers from before the PSR-4 reorganization. `AUDIT.md §3` says we will not extend it; nor should you. New OpenEMR contributions go into `src/`.

**Q: What is in `portal/`?**

The patient-facing portal — a separate UI for patients to log in, see appointments, message providers, request refills. Distinct authentication path from the staff/clinician interface. Out of scope for the Co-Pilot v1.

**Q: What is in `interface/modules/custom_modules/`?**

The supported third-party extension surface. Modules register at OpenEMR boot via an `openemr.bootstrap.php` that receives `$eventDispatcher` and `$classLoader` from core, then attaches listeners to Symfony `EventDispatcher` (PSR-14) events. Existing examples include `oe-module-claimrev-connect` (claim-revenue integration). The Clinical Co-Pilot is designed to ship as `oe-module-ai-copilot` here — `ARCHITECTURE.md §2` describes the planned file layout.

**Q: What is in `apis/`?**

Routing for OpenEMR's REST and FHIR HTTP endpoints. URLs like `/apis/default/api/...` (legacy REST) and `/apis/default/fhir/...` (FHIR R4) are dispatched through this directory. The agent's FHIR tool calls (`oe-agent-service/src/oe_agent/tools.py`) hit `http://localhost:8300/apis/default/fhir/{Patient,Observation,...}`.

**Q: What is in `ccdaservice/`?**

A Node.js sidecar that generates and parses CCDA (Continuity of Care Document) XML — the standard interchange format for transferring patient summaries between EHRs. Used for record import/export and for ONC certification. The directory is checked into this fork at `/mnt/c/Users/kenhu/gautlet/openemr/ccdaservice/`. Out of scope for the Co-Pilot v1.

**Q: What is in `gacl/`?**

The phpGACL implementation — OpenEMR's role/permission model. Controls which users can access which screens, patient categories, and data classes. `aclCheckCore('section', 'permission')` is the runtime check; `ARCHITECTURE.md §2` proposes a new `ai_copilot:use` permission gated through this system.

**Q: What is in `sql/`?**

Database schema and 50+ `*_upgrade.sql` migration scripts (`AUDIT.md` DQ-5). `sql/database.sql` is the canonical full schema. Patient/clinical tables live here (`patient_data`, `form_encounter`, `lists`, `prescriptions`, `audit_log`, etc.). The schema's polymorphism — `lists` table holds allergies + problems + medications keyed by `type` — is `AUDIT.md` DQ-2.

**Q: What is in `public/`?**

Static assets reachable from the browser without authentication: images, fonts, public-domain JS libraries, install/setup screens. The eventual chat-widget bundle (`public/js/chat-widget.js` per `ARCHITECTURE.md §2`) loads from a same-origin path so it inherits the OpenEMR session.

**Q: What is in `Documentation/`?**

User and admin documentation, install notes, ONC certification paperwork. Not where developer onboarding lives — that's `CLAUDE.md` and `CONTRIBUTING.md` in the repo root upstream.

## Patient summary screen

**Q: How is the patient summary screen structured?**

`interface/patient_file/summary/demographics.php` is the entrypoint. It composes a series of patient cards (demographics, problems, meds, allergies, recent labs, etc.) by emitting per-card Twig templates. The page is rendered by the legacy Apache/PHP request lifecycle, not a SPA.

**Q: How are cards added without forking core?**

The `patientSummaryCard.render` event is dispatched once per card slot. Custom modules attach a listener to that event, render their card via Twig, and return HTML to be injected. This is the hook `oe-module-ai-copilot` uses (`ARCHITECTURE.md §2`).

**Q: What's the frontend stack on the patient screen?**

Angular 1.8 + jQuery 3.7 + Bootstrap 4.6, bundled by Gulp 4 (`AUDIT.md §3`). Not Webpack. The Co-Pilot's chat widget will be vanilla JS (~10 kB) loaded as a same-origin script, deliberately avoiding the Angular 1.8 dependency so it can ship and update independently.

## Encounter / visit flow

**Q: How does a clinical visit become an encounter in OpenEMR?**

A clinical encounter is rooted in a row in the `form_encounter` table — date, provider, facility, encounter ID. Each clinical note or form attached to that visit lives in its own table (`form_*`) and is registered via the forms registry under `interface/forms/`. The encounter row aggregates them.

**Q: Where do clinical note types live?**

Each form type is a directory under `interface/forms/<formname>/` with its own PHP entrypoint, save handler, and view template. `EncounterService` (`src/Services/EncounterService.php`) is the modern service-layer wrapper around `form_encounter` and is what the FHIR `Encounter` resource exposes to API consumers.

**Q: What's tricky about the encounter date?**

`form_encounter.date` is sometimes stored as TEXT and is nullable (`AUDIT.md` DQ-4). The agent must accept `null` from this field and surface "I don't see a recent encounter" rather than fabricating.

## FHIR R4 / US Core API

**Q: What FHIR resources does OpenEMR expose?**

OpenEMR ships full FHIR R4 / US Core support. The agent uses `Patient`, `Encounter`, `Observation` (labs + vitals via `category`), `MedicationRequest`, `AllergyIntolerance`, `Condition`, `DocumentReference`, `Appointment`, `DiagnosticReport`, `Immunization`. Documented upstream in `FHIR_README.md`. The agent's tool table is in `ARCHITECTURE.md §3`.

**Q: How is the FHIR API authenticated?**

OAuth2 with SMART scopes. `ARCHITECTURE.md §5` selects **client credentials** for the agent service identity (machine-to-machine, isolated from clinician sessions per `AUDIT.md` AUTH-1/3/4) and a separate HMAC-signed user JWT for the end-user identity. SMART scope strings have the shape `<role>/<Resource>.<perm>` (e.g., `patient/Patient.r`).

**Q: What is `RestApiResourceServiceEvent`?**

A Symfony event that lets a custom module expose its own resource endpoints into OpenEMR's URL space without forking core. The Co-Pilot v1 doesn't use it (the agent backend is a separate FastAPI service); it's reserved for future agent-specific routes that need to live under `/fhir/*`.

**Q: Why prefer FHIR over the legacy REST API?**

Standardized resource shape across EHRs, broader tooling, US Core profile compatibility, and SMART OAuth2 scope semantics. The agent's tool layer is FHIR-only by design (`ARCHITECTURE.md §10` tradeoff 3). The legacy REST API is reserved for endpoints FHIR doesn't cover.

## Legacy REST API

**Q: What is `/api/*` for?**

Pre-FHIR REST endpoints documented in `API_README.md` upstream. Covers some OpenEMR-internal concepts (facilities, fee sheets, billing) that don't map cleanly to FHIR resources. Authentication is OAuth2 like FHIR.

**Q: Should the Co-Pilot use the legacy API?**

Not in v1. `ARCHITECTURE.md §10` explicitly chose FHIR-only for tool design and eval simplicity. Revisit only if a UC requires data the FHIR resources don't expose.

## CCDA service

**Q: What is a CCDA document?**

Continuity of Care Document — the HL7 C-CDA XML format used to transfer a patient's summary between EHRs (e.g., when a patient changes providers or gets referred). ONC certification requires CCDA import + export.

**Q: Where does CCDA live in this repo?**

`/mnt/c/Users/kenhu/gautlet/openemr/ccdaservice/` is a Node.js sidecar that handles generation/parsing. PHP code in `src/` and `interface/` invokes it over a local HTTP socket.

**Q: Is CCDA in scope for the Co-Pilot?**

No, not for v1. The agent reads structured FHIR; CCDA import/export is an OpenEMR core feature the agent does not interact with.

## Module system

**Q: How does a custom module bootstrap?**

A module ships a `moduleConfig.php` (metadata, version, ACL definitions) and an `openemr.bootstrap.php`. On core startup, OpenEMR enumerates installed modules and calls each `openemr.bootstrap.php`, passing in the Symfony `EventDispatcher` and the Composer class loader. The module attaches listeners and registers any PSR-4 namespaces it owns.

**Q: What events are most useful?**

`patientSummaryCard.render` (inject a card on the patient screen), `ScriptFilterEvent` (inject `<script>` tags via `Header::setupHeader`), `RestApiCreateEvent` / `RestApiResourceServiceEvent` (expose endpoints), and `SendNotificationEvent` (be notified when patient notifications fire). Listed in `ARCHITECTURE.md §3`.

**Q: Where will the Co-Pilot module live?**

`interface/modules/custom_modules/oe-module-ai-copilot/` per `ARCHITECTURE.md §2`. Not yet built — `progress-report.md` Part 1 lists this as designed-only.

**Q: How do modules declare ACL permissions?**

Inside `moduleConfig.php`. The Co-Pilot defines `ai_copilot:use` defaulted to allow for `Physicians`/`Clinicians` and deny for `Front Office`/`Accounting`. The bridge endpoint refuses requests where `aclCheckCore('ai_copilot', 'use')` is false.

## GACL — access control list

**Q: What is GACL?**

Generic Access Control List — the role/permission engine OpenEMR uses to gate access to screens and data classes. Implemented in `gacl/`. Roles like `Physicians`, `Clinicians`, `Front Office`, `Accounting`, `Emergency Login`, `Patient Portal`. Permissions are sectioned (`patients`, `admin`, `acct`, `encounters`, `lists`, etc.).

**Q: How does the Co-Pilot inherit ACL?**

The agent never bypasses it. The chat-bridge endpoint (`oe-module-ai-copilot/chat-bridge.php`, designed) calls `aclCheckCore('ai_copilot', 'use')` before forwarding to the agent backend, and includes the user identity in the JWT so the agent's downstream FHIR calls can be audit-logged under the real user. `ARCHITECTURE.md §5`.

**Q: What ACL gaps does the audit flag?**

`SendNotificationEvent::fetchPatientDetails()` queries `patient_data` without an ACL check (`AUDIT.md` AUTHZ-3, `src/Events/Messaging/SendNotificationEvent.php:92–96`). Listener-side `verifyAcl()` is the listener's responsibility, not core's. We compensate with edge-level CORS allow-listing and tool-scope narrowing.

## EventAuditLogger

**Q: What does `EventAuditLogger` log?**

`src/Common/Logging/EventAuditLogger.php` records access events: who accessed which `patientId`, when, with a free-text event description. Underpins HIPAA §164.312(b) audit-control compliance.

**Q: What does it not log?**

Query parameters and rationale. `AUDIT.md §1` finding §5 / §164.312(b): the audit row says "user X accessed patient Y" but not "with this query" or "for this purpose." For a deterministic SQL UI that's tolerable; for an LLM-driven access pattern, "minimum necessary" defensibility breaks down.

**Q: How does the Co-Pilot fill that gap?**

A separate `ai_copilot_audit` table (`ARCHITECTURE.md §11`) per-tool-call: user, patient, tool name, tool arguments, LLM rationale snippet, sanitized response, timestamp, trace ID. Linked to the EventAuditLogger row by request ID. This is the single highest-leverage compliance artifact the project ships and is gate 4 of the production-readiness gates.

**Q: Is audit-log encryption on by default?**

No. `EventAuditLogger.php:88–89` — encryption is gated by global `enable_auditlog_encryption` and defaults off in dev/test. Production deployments must enable it; the Co-Pilot module's README documents this.

## Portal

**Q: What is `portal/`?**

The patient portal — a distinct UI where patients (not clinicians) log in to see appointments, results, messages, and request refills. Separate authentication path from staff. `AUDIT.md` does not flag it for the Co-Pilot's scope.

**Q: Does the Co-Pilot reach the portal?**

No. `USERS.md §1` defines a single persona — a primary care physician — and `USERS.md §4` makes patient-facing experiences a non-goal for v1.

## Database layout

**Q: Where is the schema?**

`sql/database.sql` is the canonical schema. `sql/*_upgrade.sql` are 50+ migration scripts applied in version order — `AUDIT.md` DQ-5 calls schema drift a real risk and requires the eval suite to run against a freshly-upgraded DB.

**Q: What tables matter for the agent?**

`patient_data` (demographics), `form_encounter` (visits), `lists` (polymorphic — allergies + problems + medications keyed by `type`, `AUDIT.md` DQ-2), `prescriptions` (free-text dosage, `AUDIT.md` DQ-1), `form_vitals` (no unit tags — read through `VitalsService` only, `AUDIT.md` DQ-3), `audit_log`. The agent never touches these directly; it goes through `/fhir/*`.

**Q: What's the Railway-deployed DB?**

A MariaDB managed service. `deployed-to-railway.md` lines 26–45 has the project + service IDs and credentials. 52 Synthea synthetic patients loaded (PIDs 1–52, 2,752 encounters). Demo data only — no real PHI per case-study constraint.

## Admin / globals

**Q: What is `interface/super/`?**

OpenEMR's admin/superuser screens — globals editor, user management, facility config, ACL admin. Not extended by this project.

**Q: What is the `globals` table?**

Key/value store for site-wide configuration (working hours, default units, OAuth issuer URL, audit-log encryption flag, etc.). The Railway deploy patches `site_addr_oath` here at restore time so OAuth issuance points to the public URL (`deployed-to-railway.md` line 158).

**Q: What is `oe-config-database.php`?**

The bootstrap PHP that exposes DB connection details to the rest of the application. Generated at install time; lives under each site's `sites/<sitename>/sqlconf.php`. Not edited directly.

## PSR-4 services

**Q: What is `BaseService`?**

The abstract parent for service classes under `src/Services/`. Encapsulates DB access, transformation, and pagination per resource. `PatientService`, `EncounterService`, `ConditionService`, `AllergyIntoleranceService`, `ObservationLabService`, `VitalsService`, `PrescriptionService`, `ImmunizationService`, `ClinicalNotesService`, `DocumentService` all extend it.

**Q: Why does the audit flag `BaseService`?**

`AUDIT.md §2` Performance: no application-level caching. Every service call hits MariaDB. With 6+ tools per agent turn, the agent compensates with request-scoped caching and (at scale) Redis for reference data.

**Q: Why use FHIR rather than calling services directly?**

The agent backend is Python; calling PHP services in-process isn't practical. FHIR is the documented HTTP boundary, language-independent, and standardized. `ARCHITECTURE.md §10` tradeoff 3 documents the choice.

## Twig templating

**Q: Where is Twig used?**

Twig 3.x renders patient cards under `templates/patient/card/*.html.twig` (per `AUDIT.md §3`) and is the modern templating layer for patient-screen components. The legacy PHP-templating model (echo + include) still dominates older screens.

**Q: Will the Co-Pilot use Twig?**

Yes — `ARCHITECTURE.md §2` lists `templates/copilot_card.html.twig` as the chat-card shell. The chat widget JS handles dynamic UI; Twig handles the static shell that hosts it.

## Docker development environments

**Q: What's the recommended dev environment?**

`docker/development-easy/` — the OpenEMR-recommended Docker compose stack. App at `http://localhost:8300/`, HTTPS at `https://localhost:9300/`, phpMyAdmin at `http://localhost:8310/`, login `admin/pass`. Demo patients ship in.

**Q: What other Docker variants exist?**

`docker/production/` is the production-grade compose used by the Railway deploy. `docker/development-easy-redis/` adds Redis to the dev environment for testing cache integration. `docker/library/` (present in this fork at `/mnt/c/Users/kenhu/gautlet/openemr/docker/library/`) packages reusable Compose snippets.

**Q: How is the OpenEMR side deployed publicly?**

Stock OpenEMR is on Railway already at `https://openemr-production-83fe.up.railway.app` (`deployed-to-railway.md`). 52 Synthea synthetic patients loaded. The agent stack is local-only for v1.

## Test infrastructure

**Q: Where do tests live upstream?**

`tests/` at the root, with multiple PHPUnit configs: unit (`phpunit.xml`), integration (`phpunit-integration.xml`), and isolated (`phpunit-isolated.xml`). Inferno certification tests run separately.

**Q: Does this fork run upstream tests?**

Not as part of the agentic workflow. The agent stack has its own pytest suite (see Part 3). The OpenEMR PHP tests run in the upstream CI workflows (`.github/workflows/test.yml`, `isolated-tests.yml`, `inferno-test.yml`).

---

# Part 2 — Agentic AI (this fork's additions)

## What is the Clinical Co-Pilot?

**Q: In one sentence, what is this product?**

A clinical AI assistant that summarizes a patient's chart with citations, in time for a primary care physician's 90-second between-rooms transition (`USERS.md §1`).

**Q: What problem does it solve?**

Dr. M sees ~20 patients/day in 15-minute slots with ~90 seconds between rooms. They open OpenEMR, scan the chart manually, and frequently miss what changed since last visit. The Co-Pilot turns that scan into a 3-bullet, citation-grounded summary so the same physician walks in better-prepared without adding new screens to learn (`USERS.md §2`).

**Q: Who is this not for?**

Not for ED residents, hospitalists, surgical PAs, nurses, or patients themselves in v1. Single persona, single role. `USERS.md §4` is the explicit non-goals list.

## Architecture in one diagram

**Q: What's actually running today vs designed?**

Today (live): a Python/FastAPI agent service (`oe-agent-service/`) with 5 deterministic safety checks, OpenAI→Claude provider fallback, local Langfuse, the Langfuse MCP server, and stub orchestrator/voice/eval scaffolds. The OpenEMR PHP module (`oe-module-ai-copilot`) and real FHIR wiring are designed in `ARCHITECTURE.md` but not built — current tests mock FHIR via `respx`. See `progress-report.md` Part 1 for the live-component diagram.

**Q: Where do PHI flows happen?**

Browser → bridge (designed) → agent backend → Anthropic/OpenAI (BAA-assumed per case study). PHI never enters Langfuse in raw form by design (`ARCHITECTURE.md §1` boundary 3, `progress-report.md` weakest property 1: sanitizer not yet implemented). All audit/PHI surfaces map back to `AUDIT.md` PHI-1/PHI-2.

## `oe-agent-service`

**Q: Where does the code live?**

`/mnt/c/Users/kenhu/gautlet/openemr/oe-agent-service/`. Python 3.12, FastAPI, runs on port 8000. Endpoints: `POST /chat`, `GET /health`. Run with `uvicorn oe_agent.app:create_app --factory --reload`.

**Q: What's the module map?**

Per `progress-report.md` Part 1: `agent.py` (~210 lines, orchestrator), `verifier.py` (~440, 4 deterministic checks + 7 refusal-class regexes), `llm.py` (~340, OpenAI + Anthropic + fallback), `tools.py` (~140, 4 FHIR tools), `types.py` (~100, Pydantic models), `observability.py` (~25, UUID stub — Langfuse SDK not yet wired), `app.py` (~20, FastAPI factory), `config.py` (~20, pydantic-settings).

**Q: What FHIR tools does it implement?**

Four: `GetPatientSummaryTool` (`/Patient/{id}` → `patient:{uuid}`), `GetRecentLabsTool` (`/Observation?category=laboratory` → `lab:{uuid}`), `GetActiveMedicationsTool` (`/MedicationRequest?status=active` → `med:{uuid}`), `GetAllergiesTool` (`/AllergyIntolerance` → `allergy:{uuid}`). All in `oe-agent-service/src/oe_agent/tools.py`. 3-second timeout each; no retry yet (deferred per QA report).

**Q: What does a turn look like end-to-end?**

`Agent.handle_turn` in `oe-agent-service/src/oe_agent/agent.py:79` — start trace, refusal-class short-circuit (no LLM if a probe), parallel tool dispatch via `asyncio.gather`, all-tools-fail short-circuit (no LLM if every tool errors), synthesize via OpenAI primary → Claude fallback, run 4 verifier checks, return `ChatResponse`.

**Q: What are the 5 deterministic checks?**

Refusal-class (authz probes + injection on the user message), citation grounding (every cited `source_id` must come from a tool this turn), numeric grounding (response numbers match source numbers within tolerance), PHI surface (no SSN-shape strings in the response), partial-disclosure (if a `partial:tool_failure` source is present, the response must say so). All in `oe-agent-service/src/oe_agent/verifier.py`. See `progress-report.md` Part 1 for the table.

## The verifier

**Q: Why deterministic instead of LLM-as-judge?**

Two reasons (`ARCHITECTURE.md §4`): determinism — the result is reproducible across re-runs and mutation-testable; speed — runs in <500ms vs. 1-2s + per-call cost for an LLM judge. The verifier's job is to gate, not to repair (`oe-agent-service/docs/ai-usage.md`).

**Q: What are the 5 checks in code?**

- Refusal-class: `verifier._check_refusal_class` regex match against `_REFUSAL_CLASS_PATTERNS`.
- Citation grounding: `verifier._check_citation_grounding` set membership — every cited id appears in tool-returned sources.
- Numeric grounding: `verifier._check_numeric_grounding` — extract `(value, unit)` pairs, require match in source payloads.
- PHI surface: `verifier._check_phi_surface` — SSN-dashed regex + bare 9-digit regex.
- Partial-disclosure: `verifier._check_partial_disclosure` — if `partial:tool_failure` source present, response must contain a partial-data acknowledgment.

**Q: What is the synthetic source mechanism?**

When a tool returns `[]` or fails, the agent injects a synthetic citable `Source` so the LLM has a handle for honest absence-admission. Three flavors per `progress-report.md` Part 1: `empty:labs` / `empty:medications` / `empty:conditions` (tool ran, returned nothing) and `partial:tool_failure` (one or more tools 5xx'd this turn). The LLM is prompt-instructed (rules 5–10 in `oe-agent-service/src/oe_agent/llm.py:34-100`) to cite these when admitting absence — never to fabricate.

**Q: Why is `partial:tool_failure` different from `empty:*`?**

`empty:` is honest-absence (the chart truly has no labs). `partial:tool_failure` is degraded-confidence (we don't know whether the chart has labs because the labs tool errored). The verifier's `_check_partial_disclosure` enforces that the response explicitly says so — silent omission is the project's defined failure mode.

**Q: Where are the verifier's known weaknesses?**

`oe-agent-service/docs/security-pentest.md` cataloged 10 findings. Originally 4 HIGH (a `%`-class bypass in numeric grounding, a refusal-class regex too narrow, Cyrillic/leetspeak honorific evasion, and a missing PHI surface check entirely). Per the latest commit `f26096e21` the HIGH findings are closed. Three MED + 3 LOW remain documented; see `security-pentest.md` for fix sketches.

## LLM provider fallback

**Q: Why two providers?**

`oe-agent-service/src/oe_agent/llm.py:263` — `_call_with_fallback` runs OpenAI primary, falls back to Anthropic on 429 (rate limit) or 5xx (server error). Other errors (auth, 4xx other than 429) propagate immediately because they reflect caller misconfiguration that Anthropic would not fix. Single retry on a different provider, not a generic retry-with-backoff loop.

**Q: When does each provider fire?**

OpenAI fires every turn under healthy conditions. Anthropic fires only on 429/5xx. Day-to-day cost is OpenAI-only (`oe-agent-service/docs/ai-usage.md`).

**Q: What models?**

Default `gpt-4o-2024-11-20` for production synthesis, `gpt-4o-mini` for tests. Anthropic fallback uses `claude-sonnet-4-5`. Configurable via `OPENAI_SYNTHESIS_MODEL` and `ANTHROPIC_SYNTHESIS_MODEL` env vars (`oe-agent-service/src/oe_agent/llm.py:175`).

**Q: Where do the keys live?**

Repo-root `.env` (gitignored). `OPENAI_API_KEY` and `CLAUDE_API_KEY` (or `ANTHROPIC_API_KEY` as fallback). The agent service loads variables from `../.env` relative to `oe-agent-service/`.

**Q: How is it tested?**

`oe-agent-service/tests/test_llm_fallback.py`. The test forces OpenAI to raise a 429 and asserts the response comes from Anthropic without re-raising.

## Local Langfuse

**Q: What is Langfuse and why local?**

Langfuse is an LLM observability platform — traces, prompts, costs, latency. We self-host because PHI-sanitized payloads stay in our network, which is the trust-boundary commitment in `ARCHITECTURE.md §1` boundary 3 and `AUDIT.md` PHI-1.

**Q: How do I bring it up?**

`cd /mnt/c/Users/kenhu/gautlet/openemr/infra/langfuse && docker compose up -d`. Wait ~30-60s for healthy status. Web UI at port 3000 (port mapping in `infra/langfuse/docker-compose.yml`).

**Q: What's the first-login flow?**

Langfuse v2 has no seeded admin. Browse to the local UI, click Sign Up, register any email/password — the first user becomes the instance owner. After that, set `AUTH_DISABLE_SIGNUP=true` in `infra/langfuse/.env` and `docker compose up -d` to lock signup. See `infra/langfuse/README.md §2`.

**Q: Where do the API keys go?**

After login, create a project, go to Settings → API Keys, copy the public key (`pk-lf-...`) and secret key (`sk-lf-...`) immediately. Paste them into the **repo-root `.env`** (not `infra/langfuse/.env`):

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

The agent picks them up on next start.

**Q: Is the agent actually emitting traces yet?**

No — `oe-agent-service/src/oe_agent/observability.py` is a UUID stub. Real SDK trace emission is the work landing at the orchestrator level once LangGraph nodes are GREEN (`progress-report.md §4.1` phase 4). See "weakest properties" in `progress-report.md` Part 1.

**Q: Why hasn't the sanitizer been built?**

Because the trace emitter itself is a stub. The PHI sanitizer is a middleware layer that wraps the SDK call; building the wrap before the call exists doesn't make sense. It's tracked as a HIGH risk in `progress-report.md §2.10` and is part of production-readiness gate 1.

## Langfuse MCP server

**Q: What is MCP?**

Model Context Protocol — Anthropic's open spec for letting Claude Code (and other MCP clients) discover and call external tool/resource servers over a JSON-RPC channel. Each server advertises capabilities like `prompts/list`, `prompts/get`, `tools/list`.

**Q: What does this MCP server expose?**

`prompts/list` and `prompts/get` against the Langfuse Prompt Management API (`infra/langfuse/mcp-server/README.md`). It also exposes `get-prompts` and `get-prompt` as tools for clients that don't support the prompt capability natively. Only prompts with a `production` label in Langfuse are returned.

**Q: How is it wired into Claude Code?**

`/mnt/c/Users/kenhu/gautlet/openemr/.mcp.json` declares one server, `langfuse`, that runs `infra/langfuse/mcp-server/run.sh`. That script reads the Langfuse keys from the repo-root `.env` and starts the Node MCP server compiled from `infra/langfuse/mcp-server/build/index.js`.

**Q: Why aren't traces going through MCP?**

MCP is for prompt discovery from Claude Code's side — me, the developer assistant. Trace emission from the agent service itself uses the Langfuse REST API directly. Different concerns: MCP is editor tooling, REST is runtime telemetry.

## `oe-orchestrator`

**Q: What is LangGraph?**

A graph-based orchestration primitive of LangChain — typed `StateGraph`, conditional edges, checkpointing, and Send-style fanout. We use the graph primitive directly without buying into the rest of LangChain (`progress-report.md §2.12` "Why not LangChain"). Pinned to `^0.2` (test LG9 enforces).

**Q: What does the State TypedDict look like?**

`oe-orchestrator/src/oe_orchestrator/state.py` — required fields `session_id`, `user_id`, `scopes`, `transcript`; NotRequired fields populated by nodes: `intent`, `sources`, `text`, `citations`, `verifier_result`, `langfuse_trace_id`, `partial_data`, `refused`, `refusal_reason`, `audio_out`, `errors`. Single source of truth for what nodes may read or write.

**Q: How does conditional routing work?**

`oe-orchestrator/src/oe_orchestrator/graph.py:65-89`. Two conditional edges: after `refusal_class` (refused → `tts_emit`, else → `classify_intent`) and after `classify_intent` (intent → `daily_briefing` | `next_patient_brief` | `chart_question` | `tts_emit` for `out_of_scope`). All three task nodes converge on `verifier` → `tts_emit` → END.

**Q: Why hand-rolled instead of `create_supervisor`?**

`progress-report.md §4.6`. Our intent universe is bounded (4 intents); deterministic routing keeps the eval target stable. `create_supervisor` is more LLM-driven (good for novel queries), hand-rolled is more deterministic (good for our case). Revisit only if intents grow past ~10.

**Q: Is the orchestrator GREEN?**

No, RED — `oe-orchestrator/README.md` says "scaffold + 10 failing tests (LG1-LG10). Implementation lands in later phases." The graph topology is in place; node implementations raise `NotImplementedError`.

## `oe-voice-agent`

**Q: What's the pipeline?**

Browser mic → POST /voice/turn → OpenAI Whisper STT → refusal-class pre-check → rule-based intent classifier → dispatch to `oe-agent-service` → OpenAI TTS → streamed audio response. Layout in `oe-voice-agent/README.md`.

**Q: Where is the intent classifier?**

`oe-voice-agent/src/oe_voice_agent/intent.py`. Pure-Python rules, applied in order: daily_briefing keywords (brief me, today, schedule) > next_patient_brief keywords (next patient, my next, next room) > chart_question (starts with what/is/does/are/tell me OR contains `?`) > out_of_scope. Deterministic by design (no LLM).

**Q: How does the refusal-class pre-check work?**

`oe-voice-agent/src/oe_voice_agent/refusal.py` is a thin wrapper around `oe_agent.verifier`'s `_check_refusal_class`. STT transcript runs through it BEFORE intent classification — if it matches an authz probe or injection pattern, the voice agent refuses without dispatching to patient-care. Same regexes the text path uses.

**Q: STT and TTS providers?**

Whisper (`whisper-1`) for STT, `tts-1` for TTS, both via OpenAI. Voice-cassette tests use mocks; a `whisper.cpp` local fallback is on the to-do list per `progress-report.md §4.6`.

**Q: Is voice GREEN?**

RED — implementation stubs raise `NotImplementedError` except for the deterministic intent classifier and refusal-class pre-check (both are pure-Python and were trivial to land first). See `oe-voice-agent/README.md`.

## `oe-eval-agent`

**Q: What does it do?**

Polls Langfuse traces hourly via the public REST API, scores each on 5 deterministic criteria, writes a daily markdown report to `evals/results/<date>.md` and a weekly rollup to `evals/weekly/<iso-week>.md`. Cron-driven; reads-only, never modifies the live request path.

**Q: What are the 5 criteria?**

`oe-eval-agent/src/oe_eval_agent/scoring.py`:
- C1 — every-claim-cited: response has any unit-bearing numeric claim, then citations must be present.
- C2 — verifier-clean: trace's `verifier_result.failed_check` is empty.
- C3 — latency-budget: latency ≤ task budget (voice 2.5s, daily briefing 60s, next-patient 8s, chart 8s).
- C4 — no-PHI-echo: no SSN-shape PHI in the response (reuses verifier's `_PHI_SSN_DASHED_RE` and `_PHI_NINE_DIGITS_RE`).
- C5 — cost-budget: `metadata.cost_usd` ≤ task ceiling (voice $0.04, briefing $0.25, next-patient $0.03, chart $0.02).

**Q: Where do the reports land?**

`/mnt/c/Users/kenhu/gautlet/openemr/evals/results/` and `/mnt/c/Users/kenhu/gautlet/openemr/evals/weekly/`. Both directories exist; populated by the agent's daily/weekly aggregator.

**Q: Why no LLM judge here either?**

Same reason as the verifier — deterministic, reproducible, mutation-testable from trace JSON alone. `oe-eval-agent/README.md` says it explicitly: "Scoring is rule-based — no LLM judge."

**Q: Is it GREEN?**

Stubbed. `oe-eval-agent/src/oe_eval_agent/client.py` is a stub until Phase A wires the Langfuse REST fetch. Scorers are pure-functional and exercised in unit tests.

## Tests

**Q: How do I run the agent-service tests?**

```
cd /mnt/c/Users/kenhu/gautlet/openemr/oe-agent-service
pip install -e ".[dev]"
pytest
```

25 tests passing as of latest commit (`f26096e21`). Run subsets with markers — `pytest -m happy`, `pytest -m edge`, `pytest -m adversarial`, `pytest -m security`.

**Q: What's the marker convention?**

- `happy` — happy-path cases (T1).
- `edge` — boundary conditions, missing data, mutations (T2-T5, T7, T8 + variants).
- `adversarial` — refusal-class probes, prompt injection (T5 SSN, T6 ×3 prompt injection, T7 timeout).
- `security` — pen-test-style hardening (verifier % regex, PHI surface).
- `voice` — voice-path tests (V9, V10 latency-budget cases — added in Phase 2).

`progress-report.md §3` defines new markers.

**Q: How do I add a new test case?**

Create `oe-agent-service/tests/test_<topic>.py`. Follow the arrange/act/assert + docstring pattern of existing T1-T8 tests. Mark with `@pytest.mark.<marker>`. Tests must be RED before implementation, GREEN after — that's the project's TDD memory rule.

**Q: Where do the FHIR fixtures live?**

`oe-agent-service/tests/fixtures/`. respx mocks the FHIR base URL declared in `OPENEMR_FHIR_BASE_URL` (default `http://localhost:8300/apis/default/fhir`).

**Q: What's the total test count after the multi-agent expansion?**

71 (existing 25 + 46 new) per `progress-report.md §3`'s totals: voice 10, patient-care extended 13, eval 9, cross-agent 4, LangGraph 10. The 46 new are RED until the corresponding phase lands.

## Cost

**Q: What does a typical chart turn cost?**

~$0.012-$0.021 per turn at GPT-4o tier per `ARCHITECTURE.md §9`. ~6k input tokens (system prompt cached + tool outputs), 600 output tokens, 500 plan tokens, 6 internal FHIR tool calls at $0.

**Q: What about the voice and briefing tasks?**

Per `progress-report.md §2.6`: voice turn ≤ $0.04, daily briefing (25 patients) ≤ $0.25, next-patient brief ≤ $0.03. Eval agent C5 enforces these as ceilings.

**Q: Where are the budget caps in code?**

Per-task ceilings in `oe-eval-agent/src/oe_eval_agent/scoring.py:33-39` (`_COST_CEILING_USD`). The agent service itself does not yet enforce a budget cap at request time; that's tracked as a risk in `progress-report.md §2.10` and an env var `MAX_DAILY_BRIEFING_USD` is the planned mitigation.

**Q: When does Anthropic kick in?**

OpenAI 429 (rate limit) or 5xx (server error). All other errors propagate. Anthropic only serves the failover path; day-to-day cost is OpenAI-only.

**Q: How does cost scale to 10k users?**

`ARCHITECTURE.md §9` projection: at 10k users (75M turns/year), $0.9M-$1.58M/year before optimization; routing simple turns to GPT-4o-mini cuts ~50%. The architecture must change at each tier — single instance up to 100 users, Redis at 1k, model routing at 10k, self-hosted inference at 100k.

## Security

**Q: Where is the security audit of the agent?**

`/mnt/c/Users/kenhu/gautlet/openemr/oe-agent-service/docs/security-pentest.md`. 10 findings, dated 2026-04-28, scoped to `verifier.py` and `agent.py`.

**Q: What were the original 4 HIGH findings?**

1. `%` numeric claims completely bypass numeric grounding (regex `\b` anchor problem on percent sign).
2. Refusal-class regex misses many natural authz probes (e.g., "the woman in 304", "my 9 AM patient").
3. Cyrillic/leetspeak unicode evasion of the honorific pattern (`Mг. Jоnes`, `Mr. J0nes`).
4. Verifier had no PHI surface check at all — `ARCHITECTURE.md §4.3` was unimplemented.

**Q: Are they closed?**

Yes — commit `f26096e21` is "fix(agent): close HIGH findings from QA + security pen-test (25/25)". The MED and LOW findings remain documented for future work.

**Q: What about the upstream OpenEMR security gaps?**

`AUDIT.md §1` — the HIGH findings (CORS open, session cookies not HttpOnly, scope enforcement inconsistent) are out of this project's scope to fix in core. We compensate at the deployment edge (Traefik CORS allow-listing, HTTPS-only cookies, narrow per-tool scopes). Production gate 1 of 7 is verifying these are closed at the deployment edge.

## HIPAA / production readiness

**Q: Is this production-ready?**

No. Explicitly. `ARCHITECTURE.md §12` documents 7 gates that must hold before any real physician relies on this output. The MVP is a case-study deliverable, not a clinical decision tool. The module ships behind an admin-only feature flag with a "research preview" banner.

**Q: What are the 7 gates?**

`ARCHITECTURE.md §12` (5 originals) + `progress-report.md §4.4` (2 added):

1. Every `AUDIT.md` HIGH finding closed at the deployment edge (CORS, HttpOnly cookies, scope enforcement).
2. BAA executed, not assumed — Anthropic, OpenAI, Langfuse hosting, MariaDB managed service.
3. Verifier eval thresholds met — 100% on dose / allergy / numeric subset, ≥98% on overall citation grounding.
4. Per-tool-call audit row writing reliably in production with ≥30-day retention and §164.312(b) signoff.
5. Clinician-in-the-loop validation — 3+ physicians, 100+ realistic charts, ≥95% blinded-reviewer agreement.
6. Voice authentication — STT cache must purge audio after the turn; no audio persists more than 60s. Verified by an automated test.
7. Eval agent governance — every suggestion is assigned to a human owner before any code change. Auto-apply forbidden in v1.

**Q: Which HIPAA subparts are in scope?**

`AUDIT.md §5`: §164.308 (administrative safeguards), §164.312(b) (audit controls), §164.312(c) (integrity), §164.502(b) (minimum necessary), §164.514(d) (de-identification). Audit-log encryption is §164.312(a)(2)(iv) and defaults off — production must turn it on.

**Q: What's the BAA story?**

The case study lets us assume a BAA with all LLM providers (no data used for training). Production cannot. `ARCHITECTURE.md §12` gate 2 — written, signed, in counsel's hands, for every third party that touches PHI.

## How to deploy

**Q: Where does the OpenEMR fork run publicly?**

`https://openemr-production-83fe.up.railway.app` — on Railway, project `openemr-agentforge`. 52 Synthea synthetic patients loaded. Login `admin / 65c44148af66f82167b72cfa649fa669`. Full deployment notes in `/mnt/c/Users/kenhu/gautlet/openemr/deployed-to-railway.md`.

**Q: Where does the agent stack run?**

Local-only for v1. The agent service, Langfuse, orchestrator, voice, and eval all run via `docker compose` on a developer's laptop. Production deployment to Railway is on the post-MVP roadmap (`progress-report.md` Part 1 "what's NOT built").

**Q: How does the eval agent stay alive?**

It runs as a cron entry on the developer's host, invoking `python -m oe_eval_agent.cli` (`oe-eval-agent/README.md`). Hourly; output goes to `evals/results/<date>.md`. Production posture is a managed scheduler (Railway cron, GitHub Actions, or systemd timer).

**Q: How do I redeploy OpenEMR after a code change?**

There's a Claude Code skill at `.claude/skills/redeploy-openemr/` — invoke with `/redeploy-openemr` after local tests pass. It wraps `railway up --service openemr` with a smoke test against `/meta/health/readyz` and the login round-trip. See `deployed-to-railway.md` "Future deploys" section.

---

# Part 3 — How-to / runbook

## Bringing up the stack

**Q: How do I bring up the whole stack locally?**

In four terminals (or background processes):

```
# 1. OpenEMR (the EHR itself, with demo patients)
cd /mnt/c/Users/kenhu/gautlet/openemr/docker/development-easy
docker compose up --detach --wait
# App at http://localhost:8300/, login admin / pass

# 2. Langfuse (observability)
cd /mnt/c/Users/kenhu/gautlet/openemr/infra/langfuse
docker compose up -d
# UI at http://localhost:3000/ — sign up, copy keys to repo-root .env

# 3. Agent service
cd /mnt/c/Users/kenhu/gautlet/openemr/oe-agent-service
pip install -e ".[dev]"
uvicorn oe_agent.app:create_app --factory --reload
# API at http://localhost:8000/, health at /health

# 4. (RED phase, won't run yet) Orchestrator / voice / eval
# Each lives in its own pyproject.toml at oe-orchestrator/, oe-voice-agent/, oe-eval-agent/
```

**Q: What env vars are required?**

In repo-root `.env`: `OPENAI_API_KEY`, `CLAUDE_API_KEY`, `OPENEMR_FHIR_BASE_URL` (defaults `http://localhost:8300/apis/default/fhir`), `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. Optional: `OPENAI_SYNTHESIS_MODEL`, `ANTHROPIC_SYNTHESIS_MODEL`.

## Adding a tool

**Q: How do I add a new FHIR tool?**

Pattern: copy one of the four existing tools in `oe-agent-service/src/oe_agent/tools.py`. Each tool is a class with a `name` attribute and an async `call(patient_id, **kwargs) -> list[Source]` method. Wrap an `httpx.AsyncClient.get` against the FHIR base URL, parse the bundle's `entry` list, build `Source(source_id=f"<type>:{id}", source_type=..., payload=item, retrieved_at=_now())` per record. Register the tool in the `Agent` constructor's tool list.

**Q: Don't forget to:**

1. Add an entry to `_EMPTY_SOURCE_FOR_TOOL` in `agent.py:26` so empty results synthesize a citable absence marker.
2. If the new resource is in `_SCOPE_EMPTY_SOURCE` already covered by another tool, also add to `_RESOURCE_COVERED_BY_TOOL` to avoid double-synthesis.
3. Write a happy-path test mocking the FHIR endpoint via respx, plus an empty-result test and a 5xx test.

## Adding a verifier rule

**Q: How do I add a new verifier rule?**

Pattern: open `oe-agent-service/src/oe_agent/verifier.py`. Add a `_check_<name>(self, response_text, sources, request, citations) -> VerifierResult | None` method returning either a refusal verdict or `None` on pass. Wire it into `Verifier.verify` in the order you want it run (refusal-class first, then citation, then numeric, then PHI, then partial-disclosure today).

**Q: Don't forget to:**

1. Use a precompiled regex at module level — never compile in the hot path.
2. Add the refusal `failed_check` token (e.g., `rule.<name>`) to make eval-agent C2 categorize the failure.
3. Add a happy + adversarial test pair. The adversarial test should be the kind of attack that defeated the rule before it existed.
4. Update `oe-agent-service/docs/ai-usage.md` "Deterministic-only verifier checks" table.

## Tuning a prompt

**Q: How do I tune a prompt?**

Two surfaces today:

1. **Hardcoded** in `oe-agent-service/src/oe_agent/llm.py:52` (`SYSTEM_PROMPT`). Direct edit, commit, ship. This is what the agent uses today.
2. **Langfuse Prompt Management** — when fully wired, prompts are versioned in Langfuse, pulled at request time, and only `production`-labeled versions are returned (per the MCP server). Today this surface is reachable from Claude Code via the langfuse MCP server's `prompts/get`, but the agent service does not yet pull from it at runtime.

For now, edit `SYSTEM_PROMPT` in `llm.py`. Move to Langfuse Prompts once the trace emitter is real.

## Debugging a verifier failure

**Q: I got a verifier failure — how do I debug it?**

Read the response's `verifier_result.failed_check` field — that string identifies which rule fired (`refusal_class`, `citation`, `rule.numeric_grounding`, `rule.phi_surface`, `rule.partial_disclosure`). Then look at the trace: tool outputs (what the LLM had access to), the LLM's emitted text (what it said), and the citation list (what it claimed grounded each statement). The mismatch will be in one of those three.

**Q: What if the verifier is wrong?**

Reproduce in a test (see `tests/test_t4_numeric_grounding.py` for the mutation pattern). Then either tighten the rule (if the LLM was correct and the verifier was over-eager) or tighten the prompt + leave the rule strict (if the LLM was wrong and the verifier saved you). Never tighten the rule to pass a real failure mode — that's the project's defined anti-pattern.

## Flaky tests

**Q: Tests are flaky on the LLM call — what do I do?**

In tests, use `gpt-4o-mini` via the `OPENAI_SYNTHESIS_MODEL=gpt-4o-mini` env var (the default test config). Once `pytest-recording` is wired (`progress-report.md §4.3`), record a cassette with `RECORD_VCR=1 pytest -k <test>` and replay deterministically thereafter. Cassette path: `oe-agent-service/tests/cassettes/*.yaml` (planned location).

**Q: What if it's flaky in tool dispatch?**

`asyncio.gather` with `return_exceptions=True` is the parallelism primitive (see `agent.py:259`). Flakiness usually means a respx mock is missing for one of the four tools. Confirm by setting `OPENEMR_FHIR_BASE_URL` to a non-localhost value in the test env and watching for unmocked HTTP errors.

## Rotating keys

**Q: How do I rotate the API keys?**

- **OpenAI:** OpenAI dashboard → API keys → revoke old, create new. Update `OPENAI_API_KEY` in repo-root `.env`. Restart the agent service.
- **Anthropic:** Anthropic console → API keys → revoke old, create new. Update `CLAUDE_API_KEY` in repo-root `.env`. Restart the agent service.
- **Langfuse:** Langfuse UI → Settings → API Keys → create new pair. Update `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in repo-root `.env`. Restart the agent service.
- **Langfuse seed values (if recreating the Langfuse stack):** the compose file accepts `LANGFUSE_INIT_*` env vars (commit `685b1bce6` wired these for auto-seed) — set them before the first `docker compose up -d` so the stack creates its initial org/project/keys deterministically. After that, treat them as immutable for that volume.
- **Railway API token:** `https://railway.com/account/tokens`. Update wherever `RAILWAY_API_TOKEN` is set. The token in `deployed-to-railway.md` will go stale on rotation — rewrite that file.

**Q: What about the OpenEMR admin password?**

Stock OpenEMR admin lives in MariaDB. Deployed-to-railway documents the current admin/pass pair. To rotate: `railway run --service openemr` shell, then OpenEMR's standard password reset.

## Running the eval agent

**Q: How do I run the eval agent manually?**

```
cd /mnt/c/Users/kenhu/gautlet/openemr/oe-eval-agent
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m oe_eval_agent.cli
```

Output appears in `/mnt/c/Users/kenhu/gautlet/openemr/evals/results/<date>.md`. Schedule via cron once Phase A wires the Langfuse REST fetch.

**Q: How do I read the eval reports?**

Each daily file lists pass rates per criterion (C1-C5), top failures by occurrence, and concrete suggestions (failing pattern → proposed prompt/rule change). Suggestions are proposals, not auto-applied — production gate 7. Weekly rollups land in `evals/weekly/<iso-week>.md`.

## Working with the deployed OpenEMR

**Q: How do I get a shell on the Railway-deployed OpenEMR?**

`railway run --service openemr bash` after `export RAILWAY_API_TOKEN=<your token>` and `railway link --project e1ac9eee-aa15-4b50-acd5-4810e0e84965`. CLI one-liners are listed at the bottom of `deployed-to-railway.md`.

**Q: How do I tail the Railway logs?**

`railway logs --service openemr` after linking. Same authentication.

**Q: How do I redeploy after editing OpenEMR PHP?**

Use the `/redeploy-openemr` Claude Code skill. It wraps the build + smoke test. Manual fallback: `railway up --service openemr` from the repo root, then run `.claude/skills/redeploy-openemr/scripts/smoke-test.sh` against the public URL.

## Knowing when something is broken

**Q: Health checks?**

- OpenEMR: `GET /meta/health/readyz` returns 200 when DB migrations are done and Apache is serving.
- Agent service: `GET /health` returns 200 when FastAPI is up.
- Langfuse: `GET /api/public/health` returns `{"status":"OK", ...}` once Prisma migrations finish (~30-60s on first boot).

**Q: What's the smoke test for OpenEMR?**

`.claude/skills/redeploy-openemr/scripts/smoke-test.sh` — checks healthz, login GET, login POST round-trip with main_screen render. The three failure modes it covers map to known regressions: missing CryptoGen → login GET 500, audit-log AUTO_INCREMENT collision → login POST 500.

**Q: What's the smoke test for the agent?**

Run the pytest suite (`cd oe-agent-service && pytest`). 25 cases, ~10s end-to-end. If happy-path T1 passes and the LLM-fallback test passes, the core path is healthy.

## Where to look when something behaves oddly

**Q: The agent answered confidently but I think it's wrong.**

Check the trace. Open the response's `verifier_result` — was `approved=True`? If yes, the deterministic checks didn't catch it, which means either the source was actually wrong (DQ-1/DQ-2 from `AUDIT.md` — free-text fields) or one of the documented MED/LOW gaps in `security-pentest.md` (compound BP claim, citation forgery on non-numeric claims, bare numbers without units) applies. Reproduce in a test, file, fix.

**Q: The agent refused but it shouldn't have.**

Check `verifier_result.refusal_reason`. If it's `refusal_class`, the user message hit one of the regexes — usually a false positive on a real-but-suspicious phrasing. Add a regression test that asserts the legitimate phrasing approves; if the regex needs to narrow, narrow it. If it's `tool.unreachable`, every chart tool errored — check OpenEMR is up and the FHIR base URL is correct.

**Q: Latency is over budget.**

`AUDIT.md §2` is the canonical list of suspects: no application caching, N+1 risk in `AllergyIntoleranceService`, polymorphic `lists` reads. Profile via Langfuse spans — `tool_dispatch` span's `output.source_count` and per-child timings tell you which tool is slow. The fix is usually `asyncio.gather` ordering, request-coalescing, or a Redis cache for reference data.

## Other gotchas

**Q: I copy-pasted a Claude prompt into the system prompt and now nothing grounds.**

The `SYSTEM_PROMPT` in `oe-agent-service/src/oe_agent/llm.py:52` has 10 hard rules, several of which are load-bearing for verifier behavior — particularly rule 5 (absence-admission requires citing `empty:*` sources) and rule 10 (partial-data acknowledgment requires citing `partial:tool_failure`). If the LLM stops emitting these absence/partial citations, the verifier rejects every turn. Re-add the rules.

**Q: The MCP server isn't loading prompts in Claude Code.**

Three checks: (1) `infra/langfuse/mcp-server/build/index.js` exists (run `npm install && npm run build` in `infra/langfuse/mcp-server/`); (2) `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set in repo-root `.env` and `run.sh` reads them; (3) prompts are labeled `production` in Langfuse — the MCP server hides drafts.

**Q: respx mocks aren't intercepting in a new test.**

The tools default to `OPENEMR_FHIR_BASE_URL` from the environment. If a test sets a different base URL but the respx pattern matches the default, you get an unmocked passthrough. Use the same base URL the tool reads — see `tests/conftest.py` for the canonical fixture pattern.

**Q: The verifier's numeric check says my response is wrong but the source matches.**

Two known gotchas: (1) compound BP fractions (`128/78 mmHg`) only check the diastolic — `security-pentest.md` finding 7. (2) Unit class equivalence: `mg/dL` and `mg/dl` match (case-folded), but `mg` and `mg/dL` do not — by design. Look at `_UNIT_CLASSES` in `verifier.py:57`.

## PCP Testing Guide — running the agent locally

A developer-handheld walkthrough for bringing the entire stack up on a fresh laptop and exercising every endpoint the Co-Pilot currently exposes. There is no patient-facing UI yet — the chart-bridge PHP module is designed in `ARCHITECTURE.md §2` but not built — so the test surface is HTTP endpoints and audio uploads. Every command below assumes you start from the repo root at `/mnt/c/Users/kenhu/gautlet/openemr/`.

**Q: Who is this for?**

A developer (or a PCP comfortable with a terminal) standing up the stack for the first time. There is no patient-facing UI bundled in this MVP — the same-origin chart-widget script and the `patientSummaryCard.render` listener described in `ARCHITECTURE.md §2` are designed but not wired into `interface/patient_file/summary/demographics.php` yet. The test surface is therefore HTTP endpoints (`/chat`, `/tasks/daily_briefing`, `/tasks/next_patient_brief`) and audio uploads to the voice agent (`/voice/turn`). Read `USERS.md` first if you want the persona context, and skim `progress-report.md §3` for what's actually built today vs. designed.

**Q: How long does this whole walkthrough take, end-to-end?**

About 25 minutes on a fast laptop with a warm Docker cache, 50-60 minutes from a cold start (image pulls dominate). The bottleneck is the first `docker compose up` for both OpenEMR and Langfuse — together they pull ~3 GB of images. After that, the Python venvs install in under a minute each, and the `/health` and `/chat` smoke tests take seconds. Plan on a coffee break between `docker compose up -d --wait` and the rest of the steps the first time around.

**Q: What do I need installed beforehand?**

Five pieces: (1) Docker Desktop with WSL2 integration enabled (Settings → Resources → WSL Integration → toggle your distro on); (2) Python 3.11 or newer (`python3 --version` should print `3.11.x` or higher — the `oe-agent-service/pyproject.toml` floor is 3.11); (3) an `OPENAI_API_KEY` — the agent's primary LLM provider; (4) optionally a `CLAUDE_API_KEY` if you want to exercise the Anthropic fallback path documented under `## LLM provider fallback`; (5) `git`, `curl`, and `openssl` on PATH. No Node install is needed unless you plan to rebuild the Langfuse MCP server.

**Q: How do I get the code?**

```bash
git clone https://labs.gauntletai.com/lianjinhuang/patient-agent.git
cd patient-agent
```

The clone is roughly 1.2 GB once `node_modules` and the docker images cache fill in. If your GitLab credential helper isn't already configured, the clone will prompt for the lab username + access token.

**Q: How do I bring up OpenEMR locally?**

```bash
cd docker/development-easy
docker compose up -d --wait
```

The `--wait` flag blocks until the healthchecks for `openemr` and `mysql` go green (typically 60-90 seconds on first run, 10 on subsequent runs because the image is cached). Then visit `http://localhost:8300` and log in with `admin` / `pass`. If port 8300 is already taken, edit the published port in `docker/development-easy/docker-compose.yml` before bringing it up.

**Q: How do I bring up Langfuse locally?**

```bash
cd infra/langfuse
cp .env.example .env
openssl rand -hex 32  # paste output into NEXTAUTH_SECRET, then SALT, then ENCRYPTION_KEY
docker compose up -d
```

Three secrets must be regenerated separately — do not reuse one value across all three. Langfuse will land at `http://localhost:3000` (web UI) with Postgres + ClickHouse + Redis side-cars. First boot takes ~2 minutes; the full compose file is `infra/langfuse/docker-compose.yml`.

**Q: How do I get Langfuse API keys?**

Open `http://localhost:3000`, click *Sign up*, create an organization + project, then **Settings → API Keys → Create new API keys**. You'll get a public key (`pk-lf-...`) and a secret key (`sk-lf-...`). Paste both into the repo-root `/mnt/c/Users/kenhu/gautlet/openemr/.env` as `LANGFUSE_PUBLIC_KEY=` and `LANGFUSE_SECRET_KEY=`. The keys never leave the local machine, but rotate them anyway when you're done — `## Rotating keys` covers the steps.

**Q: How do I configure the .env?**

Create `/mnt/c/Users/kenhu/gautlet/openemr/.env` (same directory as `README.md`) with these fields:

```
OPENAI_API_KEY=sk-...
CLAUDE_API_KEY=sk-ant-...        # optional, only for fallback path
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
OPENEMR_FHIR_BASE_URL=http://localhost:8300/apis/default/fhir
```

The agent reads `OPENEMR_FHIR_BASE_URL` to know where FHIR lives — see `oe-agent-service/src/oe_agent/tools.py`. Both agent services auto-load this file on startup via `python-dotenv`.

**Q: How do I start the patient-care agent?**

```bash
cd oe-agent-service
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn oe_agent.app:create_app --factory --port 8000 --reload
```

The factory lives at `/mnt/c/Users/kenhu/gautlet/openemr/oe-agent-service/src/oe_agent/app.py`. Health check:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

The first install pulls ~80 packages (OpenAI SDK, httpx, FastAPI, respx, langfuse, etc.) — expect ~45 seconds.

**Q: How do I start the voice agent?**

```bash
cd oe-voice-agent
python3 -m venv .venv
.venv/bin/pip install -e ../oe-agent-service   # WSL path-dep workaround
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn oe_voice_agent.app:create_app --factory --port 8001 --reload
```

The voice service depends on `oe-agent-service` as a path dependency, but Poetry/pip on WSL sometimes can't resolve a relative file URL through the editable install — install the dependency first by hand. Factory: `/mnt/c/Users/kenhu/gautlet/openemr/oe-voice-agent/src/oe_voice_agent/app.py`.

**Q: How do I test text-mode chart summary?**

```bash
curl -sX POST http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"trace_id":"t-1","user_id":"u-1","patient_id":"1","scopes":["chart.read"],
       "messages":[{"role":"user","content":"Summarize this chart."}]}'
```

The response is a `ChatResponse` JSON envelope with `answer`, `citations`, and `verifier` fields — schema in `/mnt/c/Users/kenhu/gautlet/openemr/oe-agent-service/src/oe_agent/types.py:100`. The first call into a fresh process pays the cold-TLS hit to OpenAI (~5 s); subsequent calls are sub-second.

**Q: How do I test the daily briefing endpoint?**

```bash
curl -sX POST http://localhost:8000/tasks/daily_briefing \
  -H 'content-type: application/json' \
  -d '{"trace_id":"t-2","user_id":"u-1","scopes":["chart.read","schedule.read"],
       "date":"today"}'
```

The agent fans out across every patient on today's schedule, summarizes each chart, and returns a single rolled-up answer with `covered_patient_ids` and `missing_patient_ids` lists. See `oe-agent-service/src/oe_agent/tasks/` for the fanout implementation. If `today` returns an empty schedule, the OpenEMR demo data is the cause — seed an appointment via the OpenEMR UI at `http://localhost:8300` first, or pass an explicit `"date": "2026-04-29"` for a date you know has demo encounters.

**Q: How do I test the next-patient-brief endpoint?**

```bash
curl -sX POST http://localhost:8000/tasks/next_patient_brief \
  -H 'content-type: application/json' \
  -d '{"trace_id":"t-3","user_id":"u-1","scopes":["chart.read","schedule.read"]}'
```

Pulls the next-up patient from today's schedule (or `schedule_position: N` for the Nth slot) and returns a single-patient brief. Useful for the "I just walked into Exam 3, who's in there?" workflow — the canonical PCP daily-rhythm use case described in `USERS.md` UC-2.

**Q: How do I test voice mode?**

Record a 3-5 second WAV of a question (e.g., "What was this patient's last A1c?"):

```bash
ffmpeg -f alsa -i default -t 5 question.wav        # Linux
# or QuickTime / Voice Recorder on macOS / Windows host
curl -sX POST http://localhost:8001/voice/turn \
  -F "audio=@question.wav" -F "patient_id=1" -F "user_id=u-1" \
  --output reply.mp3 && mpv reply.mp3
```

The reply comes back as `audio/mpeg`. There is no Voice Activity Detection — the server expects a complete file, not a stream.

**Q: How do I see traces in Langfuse?**

Open `http://localhost:3000` → **Tracing → Traces**. Click any `chat_turn` row → **Spans** tab. You'll see four child spans per turn: `plan`, `tool_dispatch`, `synthesize`, `verify`. Each span carries the sanitized payload (PHI stripped by `oe-agent-service/src/oe_agent/observability.py:53`, `sanitize_payload`). If no traces appear, your Langfuse keys aren't reaching the agent — check the agent's startup log for `langfuse.client: ... initialised`.

**Q: How do I tell if the verifier rejected a response?**

In the `ChatResponse` JSON, look at `verifier.approved` (boolean) and `verifier.failed_check` (string or null). Common failed checks: `citation` (no `[CITE: ...]` in the answer), `rule.allergy` (proposed med conflicts with the patient's allergy list), `refusal_class` (the question hit a hard refusal class like prescribing). The Langfuse `verify` span carries the same payload plus the `rewrite_hint` the verifier gave the LLM if a rewrite was attempted. See `oe-agent-service/src/oe_agent/verifier.py` for the rule list.

**Q: How do I run the 30-example eval suite?**

```bash
cd evals
python3 -m venv .venv
.venv/bin/pip install -e ../oe-agent-service
.venv/bin/pip install -e .
.venv/bin/python -m evals.runner
```

The golden dataset is `/mnt/c/Users/kenhu/gautlet/openemr/evals/golden_dataset.json` (30 prompt/expected-output pairs). The runner writes a JSON report under `evals/results/`; the per-run scorer is `evals/scorer.py`. CI uploads the report as an artifact.

**Q: How do I shut everything down?**

`Ctrl-C` on the two foreground uvicorn servers, then:

```bash
cd docker/development-easy && docker compose down
cd ../../infra/langfuse && docker compose down
```

Add `-v` to either `down` if you want to drop the volumes (Langfuse traces, OpenEMR DB) — useful when you want a clean slate, lossy if you wanted to keep your eval history.

**Q: Where do I look in the logs when something fails?**

Three log streams matter: (1) the foreground uvicorn output for the agent and voice services — Python tracebacks land there immediately. (2) `docker compose logs -f openemr` from `docker/development-easy/` for FHIR-side errors (5xx from a malformed query, missing demo data). (3) `docker compose logs -f langfuse-web` from `infra/langfuse/` if traces aren't appearing — auth/encryption-key mismatch surfaces there. The agent's own structured log lines are tagged `agent.turn` / `agent.tool` / `agent.verify` and include the `trace_id` you passed in the request, so you can grep across the streams with one ID.

**Q: Can I run the integration test suite instead of curl-ing endpoints?**

Yes — `/mnt/c/Users/kenhu/gautlet/openemr/integration-tests/` exercises the live HTTP surface against a running stack. From the repo root: `cd integration-tests && python3 -m pytest -q`. The suite needs both the agent (port 8000) and OpenEMR (port 8300) up, and reads `.env` for the FHIR base URL. Use this to verify the stack end-to-end before showing it to anyone — `## Tests` covers the layered test pyramid in detail.

**Q: What goes wrong most often?**

Five frequent gotchas: (1) **Docker Desktop WSL integration off** — symptom is `docker: command not found` inside WSL even though Desktop runs on the Windows host. Fix: Settings → Resources → WSL Integration. (2) **Ports already taken** — 8300 (OpenEMR), 3000 (Langfuse), 8000 (agent), 8001 (voice). `ss -tlnp | grep :8300` to find the squatter. (3) **OPENAI_API_KEY not exported into the venv** — the venv inherits the shell environment but `python-dotenv` only reads from `/mnt/c/Users/kenhu/gautlet/openemr/.env`, not from `~/.bashrc`. (4) **Langfuse keys still empty in repo-root `.env`** — the agent silently no-ops the trace emitter when the keys are missing; you won't see a crash, you'll just see no traces. (5) **Cold-TLS hit on the first OpenAI call** adds ~5 s to the first `/chat` round-trip; not a bug, just keep-alive warm-up.

**Q: What's NOT testable yet?**

Four known gaps as of `2026-04-29`: (1) the `oe-module-ai-copilot` PHP chart-bridge module isn't built — the chat widget loads in `interface/patient_file/summary/demographics.php` is designed in `ARCHITECTURE.md §2` but no PHP listener is wired. (2) Voice Activity Detection isn't implemented — the voice agent expects a complete uploaded WAV/MP3, not a streaming microphone. (3) Production deploy of the agent stack to Railway is *documented* (`/mnt/c/Users/kenhu/gautlet/openemr/deployed-to-railway.md`) but only OpenEMR itself is deployed; the agent + voice services run locally only. (4) Per-tool retry isn't wired — a single FHIR 5xx fails the tool call rather than retrying with backoff. The orchestrator's LangGraph node (`oe-orchestrator/`) plans this but isn't on the live path.

## Glossary — technical jargon explained

This glossary exists because the project sits at the intersection of three domains a single reader rarely knows all of: U.S. healthcare IT (FHIR, HIPAA, ACL), modern web/auth plumbing (OAuth2, JWT, CORS), and LLM agent tooling (RAG, MCP, LangGraph). Each entry below gives a plain-English definition, a one-line note on how the term is used in this fork specifically, and a file path you can grep to see it in context. Terms are grouped by domain and alphabetized within each group.

### Healthcare / clinical IT

**ACL (Access Control List)** — A rules table mapping users (or roles) to the resources/actions they are permitted to access. OpenEMR ships its own ACL system, called GACL (or phpGACL), implemented under `gacl/`; the runtime check is `aclCheckCore('section', 'permission')`. `ARCHITECTURE.md §2` proposes a new `ai_copilot:use` permission so the Co-Pilot inherits OpenEMR's role-based gating instead of inventing its own.

**BAA (Business Associate Agreement)** — A HIPAA-required contract between a covered entity (a clinic) and any third party that handles PHI on its behalf. The case-study build in `ARCHITECTURE.md §11.7` *assumes* a BAA with the LLM provider; production deployment has to actually sign one with Anthropic, OpenAI, the hosting provider, and any observability vendor before live PHI flows. `ARCHITECTURE.md §13.2` lists "BAA executed, not assumed" as a HIPAA gate.

**CCDA (Continuity of Care Document)** — An XML-based clinical document standard for exchanging a patient summary between EHRs, defined by HL7. The `ccdaservice/` directory in this repo is a Node.js sidecar that generates and parses CCDA XML; OpenEMR uses it for record import/export and for ONC certification. Out of scope for the Co-Pilot v1.

**CDS (Clinical decision support)** — Software that filters or surfaces patient data to help a clinician make a decision (drug interaction warnings, dose checks, screening reminders). The Co-Pilot in this fork is a CDS tool — it does not write orders, it summarizes the chart and flags items the PCP should look at, as described in `USERS.md` use cases UC-1 through UC-5.

**CPT codes** — A procedural code set maintained by the AMA, used to bill medical/surgical/diagnostic services. We do not directly emit CPT codes from the agent, but they appear inside CCDA documents that `ccdaservice/` produces and inside `Procedure` FHIR resources that the Co-Pilot does not currently consume.

**EHR (Electronic Health Record)** — A digital, longitudinal patient record designed to be shared across organizations. OpenEMR is an open-source EHR, and `README.md` line 1 calls it that explicitly; this fork extends it with an AI co-pilot module.

**EMR (Electronic Medical Record)** — A digital chart scoped to a single practice or encounter, without the cross-organization sharing that defines an EHR. The terms are often used interchangeably in marketing copy, but the practical distinction is interoperability: an EHR speaks FHIR/CCDA outward, an EMR typically does not. We refer to OpenEMR as an EHR throughout `README.md` and `ARCHITECTURE.md` because of its FHIR R4 + US Core support.

**FHIR (Fast Healthcare Interoperability Resources)** — An HL7 standard for exchanging healthcare data as RESTful JSON resources (Patient, Observation, Condition, MedicationRequest, etc.). OpenEMR exposes FHIR R4 with US Core profiles at `/apis/default/fhir/...`; the agent's tool layer (`oe-agent-service/src/oe_agent/tools.py`) hits exactly those endpoints. `ARCHITECTURE.md §3` row "Data access" makes this the canonical data shape for the agent.

**HIPAA** — The U.S. Health Insurance Portability and Accountability Act, which sets rules for PHI handling. The clauses we care about: §164.312(b) (audit trail of who accessed what PHI when) is satisfied by OpenEMR's `EventAuditLogger`, and §164.308 (administrative safeguards) is what BAAs operationalize. `ARCHITECTURE.md §12` and `progress-report.md §4.4` enumerate the HIPAA gates this fork must clear.

**HL7** — Health Level Seven International, the standards body that publishes FHIR and, before it, the v2 messaging standard and the CDA/CCDA document standards. We use FHIR R4 (the modern HL7 standard) for all live data access; CCDA (the older HL7 document format) is touched only via the `ccdaservice/` sidecar.

**ICD-10** — A diagnosis-code vocabulary maintained by the WHO; the U.S. clinical modification (ICD-10-CM) is what U.S. EHRs use. ICD-10 codes appear inside FHIR `Condition.code` resources that the agent reads via `tools.fetch_conditions`; the agent never invents codes, only quotes them from the FHIR payload.

**LOINC** — A universal coding system for laboratory and clinical observations, maintained by the Regenstrief Institute. LOINC codes appear inside `Observation.code` for lab results that the agent reads via `tools.fetch_labs`; numeric grounding in `verifier.py` is what enforces that the agent's reported A1c value matches the LOINC-coded source.

**NPI (National Provider Identifier)** — A 10-digit U.S. provider identifier issued by CMS, used on every claim and on every prescription. We do not currently verify NPIs in the agent, but a future practitioner-identity check (e.g., for delegated-prescribing audit) would key on this — see the "future verifier concern" thread in `progress-report.md`.

**PCP (Primary Care Physician)** — The clinician a patient sees first for routine care, who coordinates referrals to specialists. `USERS.md` defines "the busy PCP" as the single target persona for the Co-Pilot — five concrete use cases, explicit non-goals.

**PHI (Protected Health Information)** — Any individually identifiable health information covered under HIPAA: names, dates, MRNs, diagnosis codes tied to an identifiable person, etc. Our PHI sanitizer (`oe-agent-service/src/oe_agent/observability.py:53`, `sanitize_payload`) walks every payload before it leaves the process for Langfuse, scrubbing identifiable fields so traces never carry PHI.

**RxNorm** — A normalized drug-naming vocabulary maintained by the U.S. National Library of Medicine. RxNorm codes appear inside FHIR `MedicationRequest.medicationCodeableConcept` and are how the agent identifies a drug independently of brand/generic naming variation; the `tools.fetch_medications` path returns these.

### Database / storage

**JSON column / JSONB** — A column type that stores JSON natively in the database, with operators for path lookup. OpenEMR's MariaDB schema does not store FHIR resources as JSON columns today (it shreds them across relational tables under `sql/database.sql`); a future caching layer for `oe-agent-service` could persist FHIR payloads as JSONB in Postgres alongside Langfuse, but that is not implemented.

**MariaDB** — A community fork of MySQL maintained by MySQL's original developers after Oracle's 2009 acquisition; SQL syntax and wire protocol are MySQL-compatible. OpenEMR uses MariaDB as its primary store — see the `mysql` service in `docker/development-easy/docker-compose.yml` and `ARCHITECTURE.md §3` line 62. Some MariaDB-specific features (window functions, JSON helpers) are used by the schema, which is why "swap in MySQL" is not a free migration.

**PostgreSQL** — A separate open-source relational database. We use Postgres only for Langfuse self-hosting (`infra/langfuse/docker-compose.yml`) and would use it for LangGraph's `PostgresSaver` checkpointer in phase F (`oe-orchestrator/src/oe_orchestrator/checkpoint.py:33`). OpenEMR itself does not use Postgres.

**SQL migration** — A versioned script that evolves the database schema forward (and ideally back). OpenEMR ships 50+ `*_upgrade.sql` files under `sql/` — see `AUDIT.md` finding DQ-5 — and `sql/database.sql` is the canonical full schema; new fields land via a new `*_upgrade.sql` rather than editing the canonical schema in place.

### Web / API

**CORS (Cross-Origin Resource Sharing)** — A browser security mechanism that controls whether a page from origin A can read responses from origin B. OpenEMR's `CORSListener` reflects the request's `Origin` header back unconditionally — `AUDIT.md` AUTHZ-1 (HIGH), `src/RestControllers/Subscriber/CORSListener.php:53–73`. Production deployment must restrict CORS at the edge to a known origin list before any live PHI flows.

**CSRF (Cross-Site Request Forgery)** — An attack where a malicious site causes a logged-in user's browser to submit a request to a target site under the user's authority. OpenEMR mitigates CSRF with per-form tokens validated server-side; `ARCHITECTURE.md §6` line 208 notes the browser-to-chat-bridge channel is trusted via OpenEMR session cookie *plus* CSRF token.

**HttpOnly cookie** — A cookie flag that hides the cookie from JavaScript, blocking XSS-driven cookie theft. OpenEMR's core session cookies are *not* `HttpOnly` (`SessionConfigurationBuilder.php:88`, `setCookieHttpOnly(false)`) — that is `AUDIT.md` SESS-1 (HIGH). The agent backend therefore authenticates via a Bearer JWT, never the user's session cookie, which contains the blast radius.

**JWT (JSON Web Token)** — A compact, signed JSON payload used as a bearer credential; HMAC-signed JWTs are verified with a shared secret. In our architecture, `oe-module-ai-copilot/chat-bridge.php` issues a 5-minute JWT carrying `{user_id, patient_id, scopes}` HMAC-signed with a shared secret; the agent backend trusts only that JWT (`ARCHITECTURE.md §6` lines 73, 202, 209).

**OAuth2** — An authorization-delegation standard that issues short-lived bearer tokens to clients. We use two grants: **client_credentials** for the agent backend's identity to OpenEMR's FHIR API (machine-to-machine, narrow scopes per tool — `ARCHITECTURE.md §3` and §6 line 210), and **authorization_code** is OpenEMR's existing user-facing OAuth2 grant that we do *not* add to.

**REST** — An architectural style for HTTP APIs where resources have URLs and verbs (GET/POST/PUT/DELETE) map to operations. OpenEMR's `/apis/default/api/...` and `/apis/default/fhir/...` are REST (not GraphQL or RPC); routing lives under `apis/`, and the agent's tool layer is a thin REST client.

**Same-origin proxy** — A deployment posture where the browser-facing app and its backend share a single origin, so the browser sees one host and CORS is moot. `ARCHITECTURE.md §1` and §6 require the chat widget JS and the chat-bridge endpoint to live on the OpenEMR origin so the session cookie attaches automatically and the agent backend is never exposed cross-origin.

**TLS / HTTPS** — Transport encryption that protects data in flight. We assume HTTPS at the edge (reverse proxy / load balancer terminating TLS); `AUDIT.md` SESS-2 makes the `Secure` cookie flag dependent on edge TLS, and `ARCHITECTURE.md §6` line 207 lists HTTPS-only as a deployment gate.

### LLM / AI

**AI Agent** — In this project, an "agent" is the four-part composition: an LLM that reasons, a set of tools it can call, a deterministic verifier that checks every claim, and an orchestrator (LangGraph) that wires the steps together. `ARCHITECTURE.md §1` defines the verifier as the "single most important architectural decision" — without it, an agent is just a chatbot.

**Claude / GPT** — Claude is Anthropic's family of LLMs (Sonnet, Opus, Haiku); GPT is OpenAI's family (GPT-4o, GPT-4o-mini, etc.). We use OpenAI as the primary synthesis model with an Anthropic fallback path — see `oe-agent-service/src/oe_agent/llm.py:286` (`openai_fn` and `anthropic_fn` arguments to the fallback wrapper).

**Context window** — The maximum number of tokens an LLM call can hold across input + output. GPT-4o has a 128k context window; Claude Sonnet 4 has 200k natively and offers a 1M-context tier. `ARCHITECTURE.md §11.7` calls out losing the 1M-context option as a tradeoff of choosing OpenAI for v1.

**Embedding** — A fixed-length numeric vector representing the semantic content of a piece of text, used for similarity search. We do not currently use embeddings — the FHIR API gives us structured retrieval, so semantic search over free-text notes is deferred to v2 along with vector storage.

**Function calling / tool use** — The LLM-side feature where the model emits a structured JSON tool-call instead of free text, and the host runtime dispatches it. We use this through Pydantic AI inside individual nodes (`oe-agent-service/src/oe_agent/agent.py`) so the synthesis model returns a typed `SynthesisOutput` rather than a string we have to re-parse.

**Grounding / citation grounding** — The requirement that every factual claim in the LLM's output be backed by a tool result returned in the same turn. Our verifier (`oe-agent-service/src/oe_agent/verifier.py`) enforces this: a claim with no citation, or a citation whose source does not contain the asserted value, fails grounding — see `ARCHITECTURE.md §4.1`.

**Hallucination** — When an LLM emits a confident statement that is not supported by any source. The verifier exists *because* hallucination is the central failure mode for medical applications; `ARCHITECTURE.md §1` frames the whole verification layer as the answer to "what stops a confidently-stated hallucination?"

**LLM (Large Language Model)** — A neural network trained on vast text corpora that can generate plausible continuations and follow instructions. In this project the LLM is the synthesis brain — it does not access PHI directly; it reads tool results that the FHIR layer fetches.

**Prompt caching** — A provider-side optimization that lets you reuse a long static prefix (system prompt + tool schemas) across many calls at a deep discount. Anthropic offers ~90% cache-read discount; OpenAI ~50%. `ARCHITECTURE.md §10` lines 300–318 work the cost analysis: at the 1k-user tier, prompt caching is the difference between $0.021 and $0.012 per turn.

**RAG (Retrieval-Augmented Generation)** — A pattern where the LLM is given relevant external data at inference time instead of relying on its training corpus. The Co-Pilot is RAG-shaped: the FHIR tool layer is the retriever, the LLM is the generator, and the verifier post-checks that the generation actually used the retrieved sources — see `ARCHITECTURE.md §3` and §4.

**Structured output / JSON mode** — A provider feature that forces the model to emit JSON conforming to a schema, instead of free text. We use OpenAI's `response_format=SynthesisOutput` (`oe-agent-service/src/oe_agent/llm.py:323`) so synthesis returns a typed `text + cited_claims` payload directly.

**Temperature** — A sampling parameter from 0 to 1+ that controls how random the LLM's output is. We pin synthesis to `temperature=0.1` (`oe-agent-service/src/oe_agent/llm.py:324`) — close to deterministic — because the verifier's repeatability assumptions break down at higher temperatures.

**Token** — The atomic unit of LLM input and output, roughly 3-4 characters of English; pricing is per million tokens. `ARCHITECTURE.md §10` does the cost arithmetic in tokens: ~3.5k input + ~500 output per turn, multiplied by the user-tier traffic curve.

**Vector database** — A specialized store for embedding vectors with similarity search. We do not run one today (no embeddings, no semantic search); deferred for v2 along with free-text-note retrieval.

### Agent frameworks

**Checkpoint** — A LangGraph mid-flow save of graph state, used to resume or replay. `oe-orchestrator/src/oe_orchestrator/checkpoint.py` returns a `MemorySaver` (in-memory) for tests; `langgraph-checkpoint-postgres.PostgresSaver` is a phase-F deliverable, currently unwired (`checkpoint.py:33`).

**Conditional edge** — A LangGraph edge whose target depends on a routing function over the current state, not a fixed destination. We use these to route by detected intent: `g.add_conditional_edges(...)` at `oe-orchestrator/src/oe_orchestrator/graph.py:68` and `:80` is what selects the right node based on whether the request is a chart summary, a med-check, etc.

**LangChain** — A broad umbrella of LLM tooling (chains, retrievers, memory primitives, agent loops) by the company of the same name. We do not buy into the LangChain agent abstraction; we use only LangGraph (a state-graph primitive that ships in the same ecosystem) and write the rest ourselves.

**LangGraph** — A library for expressing agent flows as a state graph: nodes are functions over a typed `State`, edges are transitions, and the runtime drives the graph until it hits `END`. Our orchestrator is built on it — `from langgraph.graph import END, StateGraph` at `oe-orchestrator/src/oe_orchestrator/graph.py:25`, with `StateGraph(State)` at line 51.

**MCP (Model Context Protocol)** — An open standard introduced by Anthropic in November 2024 for how LLMs talk to external tool/data servers, eliminating per-vendor connectors. Our Langfuse MCP server is vendored at `infra/langfuse/mcp-server/` (commit 23eddc19f) and lets a Claude client read/write Langfuse prompts via MCP; see `infra/langfuse/mcp-server/README.md`.

**Pydantic AI** — A Python library that wraps LLM calls in Pydantic models so the model output is parsed/validated as a typed object instead of a string. We use it inside synthesis nodes (`oe-agent-service/src/oe_agent/llm.py` defines `SynthesisOutput(BaseModel)` at line 45) so a malformed model response surfaces as a Pydantic validation error rather than as silently bad data.

**State machine** — A computational model where the system is always in one of a finite set of states and transitions are explicit. LangGraph's `StateGraph` is, conceptually, a state machine over a typed state object — it is the explicit-transition shape that lets us reason about and test the orchestrator's flow at `oe-orchestrator/src/oe_orchestrator/graph.py`.

### Observability / eval

**Adversarial testing** — Test cases that try to break the system the way an attacker would, rather than the way a benign user would. T6 (`oe-agent-service/tests/test_t6_prompt_injection.py`) is our adversarial suite: clinical notes carry embedded prompt injections trying to leak SSNs, swap roles, or override structured medication doses.

**Eval / evaluation suite** — A test suite that scores LLM/agent quality automatically on a fixed dataset. Our eval lives in `oe-agent-service/tests/` (the T1–T8 files) plus `oe-eval-agent/` for the live-traffic scoring loop; `ARCHITECTURE.md §3` row "Eval" sets the bar at "running it in CI on every push."

**Langfuse** — An open-source LLM observability platform (traces, spans, evaluations, prompt management). We self-host it via `infra/langfuse/docker-compose.yml`; the client wrapper lives at `oe-agent-service/src/oe_agent/observability.py` and includes the PHI sanitizer that scrubs payloads before they leave the process.

**Mutation testing** — A testing technique where you flip a value in the source data and assert the test now fails — proving the test was actually checking that value. T4's `numeric_grounding_mutation_caught_by_verifier` (`oe-agent-service/tests/test_t4_numeric_grounding.py:74`) does exactly this for the verifier: the lab value mutates from 7.2 to 7.3 and the verifier must catch it.

**Pen-test (penetration testing)** — A security review that actively probes for exploits rather than reviewing code statically. `oe-agent-service/docs/security-pentest.md` is our agent-side pen-test report; the four HIGH findings from it are now closed (commit f26096e21).

**Promptfoo** — A popular open-source eval harness for LLM apps, with assertion DSL and a web UI. `ARCHITECTURE.md §3` row "Eval" mentions Promptfoo as the design intent, but our actual eval today is Pytest-based — Promptfoo adoption is deferred.

**Pytest** — The standard Python testing framework; it is what actually runs our eval suite today. Each test in `oe-agent-service/tests/` is a Pytest case; `oe-agent-service/pytest.ini` configures the runner.

**Trace / span** — Units of observability borrowed from distributed tracing: a *trace* is one request end-to-end, a *span* is one step inside it, and spans nest. Langfuse stores LLM-flavored traces (model, tokens, latency, cost) keyed by request — see `oe-agent-service/src/oe_agent/observability.py` for how we instrument them.

### DevOps / runtime

**Cron / scheduled job** — A unix utility that runs commands on a schedule; broadly, any time-triggered job. The eval agent's CLI is meant to be run hourly from cron — `oe-eval-agent/src/oe_eval_agent/cli.py` line 5 explicitly says "exits 1 with a clear message rather than crashing the cron host," and `oe-eval-agent/src/oe_eval_agent/alerts.py:50` notes the "~hourly" cadence.

**Docker / docker-compose** — Container runtime and multi-container orchestrator (`docker compose up` brings up a stack of services). OpenEMR runs from `docker/development-easy/docker-compose.yml`; Langfuse runs from `infra/langfuse/docker-compose.yml`. Local dev is `docker compose up -d` in either directory.

**pytest-recording / VCR** — Cassette-based test recording: capture real HTTP calls once, replay deterministically thereafter. We document this as the eventual recording strategy in `oe-agent-service/docs/` but currently use `respx` for mocking; cassette adoption is deferred.

**Railway** — A managed cloud hosting platform. The OpenEMR demo is deployed to Railway (`deployed-to-railway.md`); the agent stack is local-only today. Note `deployed-to-railway.md` warns it contains credentials and a Railway API token.

**respx** — A Python mock library specifically for the `httpx` HTTP client. Our test suite mocks every FHIR call through it — `import respx` at `oe-agent-service/tests/conftest.py:13`, with the `fhir_mock` fixture at line 51 creating a `respx.MockRouter` that targets the OpenEMR FHIR base URL.

**WSL (Windows Subsystem for Linux)** — A Microsoft compatibility layer that runs an Ubuntu-flavored Linux userland on Windows. The repo's working tree lives at `/mnt/c/Users/kenhu/gautlet/openemr/` — the `/mnt/c/` prefix is the Windows C: drive surfaced inside WSL — which is why every absolute path in this repo starts that way.

### Voice / multimodal (v2)

**STT (Speech-to-Text)** — Converting spoken audio to written text. `oe-voice-agent/src/oe_voice_agent/stt.py` is the OpenAI Whisper client wrapper; the pipeline (`oe-voice-agent/src/oe_voice_agent/app.py:30`) is `STTClient.transcribe -> text`.

**TTS (Text-to-Speech)** — The reverse: rendering text as spoken audio. `oe-voice-agent/src/oe_voice_agent/tts.py` wraps OpenAI's TTS API with the `tts-1` model (`oe-voice-agent/src/oe_voice_agent/config.py:22`).

**WebRTC** — A browser standard for real-time audio/video capture and peer-to-peer streaming, exposed via JavaScript APIs. The voice agent's planned browser side captures the mic via WebRTC and POSTs an audio blob to `/voice/turn` — see the pipeline notes in `oe-voice-agent/README.md` line 5.

**Whisper** — OpenAI's open-weights speech-recognition model, also offered as a hosted API. We use the hosted version for STT in `oe-voice-agent/src/oe_voice_agent/stt.py` (file docstring: "OpenAI Whisper STT client wrapper").

## What to read next

**Q: I want to understand the design decisions.**

`/mnt/c/Users/kenhu/gautlet/openemr/ARCHITECTURE.md` end-to-end. Then `AUDIT.md §6` "What we would have missed without the audit."

**Q: I want to understand what's actually built.**

`/mnt/c/Users/kenhu/gautlet/openemr/progress-report.md` Part 1 — module map and current vs designed.

**Q: I want to understand the user.**

`/mnt/c/Users/kenhu/gautlet/openemr/USERS.md`. One persona, five use cases, explicit non-goals.

**Q: I want to understand the security posture.**

`/mnt/c/Users/kenhu/gautlet/openemr/AUDIT.md §1` (upstream OpenEMR security gaps) + `/mnt/c/Users/kenhu/gautlet/openemr/oe-agent-service/docs/security-pentest.md` (verifier hardening). The 4 HIGH findings are now closed; MED + LOW remain documented.

**Q: I want to understand HIPAA / production readiness.**

`/mnt/c/Users/kenhu/gautlet/openemr/ARCHITECTURE.md §12` (5 original gates) plus `/mnt/c/Users/kenhu/gautlet/openemr/progress-report.md §4.4` (2 added gates for voice + eval governance).

**Q: I want to understand the deployment.**

`/mnt/c/Users/kenhu/gautlet/openemr/deployed-to-railway.md` for OpenEMR on Railway. Agent stack is local-only — see Part 3 "Bringing up the stack" above.

**Q: I just want to demo it.**

`docker compose up -d` in `docker/development-easy/`, hit `http://localhost:8300/`, log in `admin/pass`, open a patient. Then `cd oe-agent-service && uvicorn oe_agent.app:create_app --factory --reload` and `curl -X POST localhost:8000/chat -d '{...}'` with a valid `ChatRequest` body. The browser-side Co-Pilot card is not yet built — the request/response is via `curl` for now.
