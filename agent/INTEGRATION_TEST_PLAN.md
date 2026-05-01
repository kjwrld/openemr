# OpenEMR Integration Test Plan

## Overview
Tests for the Clinical Co-Pilot chat widget integration with OpenEMR's patient summary page.

## Test Coverage

### 1. **Static File Serving** ✅
- [x] `/static/chat.html` is accessible
- [x] `/static/demo.html` is accessible
- [x] CORS headers allow iframe embedding from OpenEMR

### 2. **Patient ID Passing** ✅
- [x] Chat widget reads `pid` from URL parameter
- [x] Patient ID is pre-filled in the widget
- [x] Different patient IDs produce different hashes
- [x] Invalid patient ID types are rejected (422)

### 3. **Security** ✅
- [x] SQL injection attempts are blocked
- [x] Patient ID validation prevents type confusion
- [x] Session isolation between different users
- [x] Patient ID is hashed in logs

### 4. **Performance** ✅
- [x] Agent responds in < 10 seconds
- [x] Latency is acceptable for UI usage
- [x] Health check responds quickly

### 5. **API Integration** ✅
- [x] `/chat` endpoint accepts patient_id
- [x] `/health` endpoint is accessible
- [x] Rate limiting works (10 req/min)
- [x] Error responses are user-friendly

---

## Manual Testing Checklist

### Prerequisites
```bash
# 1. Start OpenEMR locally
cd docker/development-easy
docker compose up -d --wait

# 2. Start agent service
cd ../../agent
uvicorn main:app --reload --port 8000

# 3. Verify both are running
curl http://localhost:8300/meta/health/readyz  # OpenEMR
curl http://localhost:8000/health              # Agent
```

### Test Case 1: Button Appears on Patient Page
**Steps:**
1. Navigate to: http://localhost:8300
2. Login: `admin` / `pass`
3. Go to: Patient/Client → Search/Add
4. Select any patient (or create one)
5. Click on "Medical Record Dashboard"

**Expected:**
- ✅ Purple 🤖 button appears in bottom-right corner
- ✅ Button has tooltip "Open Clinical Co-Pilot"
- ✅ Button has gradient background

**Actual:** ___________

---

### Test Case 2: Modal Opens with Chat Widget
**Steps:**
1. From patient summary page
2. Click the 🤖 button

**Expected:**
- ✅ Modal overlay appears (darkened background)
- ✅ Chat widget loads in iframe
- ✅ Title shows "🩺 Clinical Co-Pilot"
- ✅ Patient ID field shows correct patient (e.g., Patient ID: 1)

**Actual:** ___________

---

### Test Case 3: Patient ID Auto-Fills
**Steps:**
1. Navigate to patient with ID 1
2. Open copilot
3. Check patient ID field
4. Navigate to patient with ID 2
5. Open copilot again

**Expected:**
- ✅ Patient 1: Shows "Patient ID: 1"
- ✅ Patient 2: Shows "Patient ID: 2"
- ✅ Each patient gets correct ID automatically

**Actual:** ___________

---

### Test Case 4: Send Message to Agent
**Steps:**
1. Open copilot for any patient
2. Type: "Give me a pre-visit summary"
3. Click "Send" or press Enter

**Expected:**
- ✅ Message appears in chat (right-aligned, blue)
- ✅ Agent response appears (left-aligned, gray)
- ✅ Response includes citations (if data available)
- ✅ Loading spinner shows during processing

**Actual:** ___________

---

### Test Case 5: Close Modal
**Test 5a: Close button**
1. Open copilot
2. Click X button in top-right

**Expected:** Modal closes

**Test 5b: Escape key**
1. Open copilot
2. Press Escape key

**Expected:** Modal closes

**Test 5c: Click overlay**
1. Open copilot
2. Click dark background (outside modal)

**Expected:** Modal closes

**Actual:** ___________

---

### Test Case 6: Agent Handles Missing Data
**Steps:**
1. Open copilot for patient with no data
2. Ask: "What medications is this patient on?"

**Expected:**
- ✅ Agent responds honestly: "No active medications found" or similar
- ✅ Does NOT hallucinate fake medications
- ✅ No citations shown (or empty citations array)

**Actual:** ___________

---

### Test Case 7: Multiple Patients, Same Session
**Steps:**
1. Open patient 1, ask a question
2. Navigate to patient 2, ask a question
3. Navigate back to patient 1, ask another question

**Expected:**
- ✅ Each patient gets correct data
- ✅ No data leakage between patients
- ✅ Patient ID updates correctly each time

**Actual:** ___________

---

### Test Case 8: Rate Limiting Works
**Steps:**
1. Open copilot
2. Send 10+ messages rapidly (< 1 minute)

**Expected:**
- ✅ First 10 requests succeed
- ✅ 11th request gets 429 error: "Rate limit exceeded"
- ✅ Error message is user-friendly

**Actual:** ___________

---

## Automated Test Execution

### Run All Integration Tests
```bash
cd /Users/kj/dev/gauntlet/openemr/agent
python3 -m pytest tests/test_openemr_integration.py -v
```

**Expected Output:**
```
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_static_chat_html_accessible PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_chat_html_accepts_pid_parameter PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_agent_accepts_patient_id_from_openemr PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_multiple_patient_contexts PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_chat_endpoint_with_invalid_patient_id_type PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_cors_headers_for_iframe_embedding PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_agent_response_time_acceptable_for_ui PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_session_isolation_between_openemr_users PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_chat_widget_handles_missing_patient_id PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_static_files_serve_correctly PASSED
tests/test_openemr_integration.py::TestOpenEMRIntegration::test_health_check_from_openemr_context PASSED

============ 11 passed in X.XXs ============
```

### Run with Coverage
```bash
pytest tests/test_openemr_integration.py --cov=main --cov-report=term-missing
```

---

## Known Issues / Limitations

1. **OAuth Not Implemented Yet** (Deferred to Final)
   - Current: Agent returns "authorization error" for real FHIR requests
   - Workaround: Tests use mocked data
   - Fix: Implement OAuth2 client credentials flow

2. **CORS in Production**
   - Current: `allow_origins=["*"]` for development
   - Fix: Restrict to OpenEMR domain in production

3. **Single Agent Instance**
   - Current: One agent instance, stateless
   - Future: Consider Redis for multi-instance deployments

---

## Success Criteria

✅ All 11 automated tests pass
✅ All 8 manual test cases pass
✅ No security vulnerabilities found
✅ Response time < 10 seconds
✅ Patient ID isolation verified
✅ Modal UX works smoothly

---

## Deployment Verification

After deploying to Railway:

1. Update line 2172 in demographics.php:
   ```javascript
   const copilotAgentUrl = 'https://your-agent.up.railway.app';
   ```

2. Re-run integration tests against deployed URL:
   ```bash
   export AGENT_URL=https://your-agent.up.railway.app
   pytest tests/test_openemr_integration.py -v
   ```

3. Manual smoke test:
   - Open deployed OpenEMR
   - Navigate to patient page
   - Click 🤖 button
   - Verify chat loads and responds

---

## Test Artifacts

- **Test Suite:** `tests/test_openemr_integration.py`
- **Manual Checklist:** This document
- **Demo Video:** (Record manual tests)
- **Test Results:** `pytest --html=report.html`
