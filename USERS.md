# Clinical Co-Pilot: Target Users & Use Cases

## Target User Profile

**Primary User: Primary Care Physician (PCP) in Outpatient Setting**

### Demographics
- **Specialty:** Internal Medicine, Family Medicine
- **Practice Setting:** Community health clinic with 8 physicians, 4,200 active patients
- **Daily Schedule:** 18-22 patient appointments, 9:00 AM - 5:00 PM
- **Average Time per Patient:** 15-20 minutes (includes documentation time)
- **Time Between Patients:** 60-90 seconds to review next patient before entering room

### Technical Profile
- **EHR Experience:** 6+ years with OpenEMR (moderate proficiency)
- **Typing Speed:** 45-60 WPM
- **Comfort with Technology:** Moderate (uses smartphone apps, email, basic keyboard shortcuts)
- **Current Tools:** OpenEMR patient chart, UpToDate for clinical references, occasional Google searches

### Pain Points

**1. Information Overload**
- Patient charts span 5-15 years of history (hundreds of notes, lab results, medications)
- Chronic disease patients have 20+ active problems, 8-12 medications, dozens of lab trends
- Physician must synthesize this into coherent context in <90 seconds between patients

**2. Context Switching**
- Between patients: Close current chart → Open next chart → Scan demographics → Review vitals → Check medications → Read last visit note → Formulate visit plan
- Mental model reset every 15 minutes (18-22 times per day)
- No time to deeply review history; relies on memory from previous visits

**3. Documentation Burden**
- 20-30% of appointment time spent typing notes (physician looks at keyboard, not patient)
- Copy-paste from previous notes leads to outdated information in chart
- Fear of missing critical information (abnormal lab result buried in 3-month history)

**4. Critical Information Buried**
- Recent A1C is elevated → buried in 47 lab results over 3 years
- Patient mentioned chest pain in last visit → buried in 8-paragraph SOAP note
- New medication started 2 weeks ago → not visible in "active medications" summary (coded as pending)

### Daily Workflow

**8:50 AM - Pre-Clinic Preparation**
- Arrive at clinic, log into OpenEMR
- Review today's schedule (20 patients)
- Scan for "high-risk" patients (diabetes with overdue A1C, patients with recent ER visits)
- **Current process:** Manually click each patient, scan chart, make mental note
- **Time required:** 15-20 minutes for 20 patients (45-60 seconds per patient)

**9:00 AM - Patient Appointments Begin**
- Between each patient:
  - Previous patient checkout (30 seconds)
  - Walk to next exam room (15 seconds)
  - **Chart review window: 60-90 seconds**
  - Enter room, greet patient (workflow continues)

**Chart Review Window Breakdown (90 seconds):**
1. Open patient chart (5 sec)
2. Verify demographics (name, DOB, allergies) (5 sec)
3. Check vitals (BP, weight, temp) (10 sec)
4. Scan active medications (15 sec)
5. Review problem list (10 sec)
6. Read last visit note (30 sec)
7. Check pending labs/orders (10 sec)
8. Formulate visit plan (5 sec)

**Total: 90 seconds** - No buffer for unexpected findings

**5:00 PM - End of Day Documentation**
- Finish charting for last 3-4 patients (deferred due to time constraints)
- Review lab results that came in during day
- Refill prescription requests
- **Time required:** 30-60 minutes of unpaid overtime

---

## Use Cases

### Use Case 1: Pre-Visit Summary (8:50-9:00 AM Window)

**Description:**

Between 8:50 and 9:00 AM, physician opens the chart for the next patient on today's schedule. The agent provides a 4-6 sentence summary that highlights:
1. **Patient snapshot:** Name, age, gender, chief complaint for today's visit
2. **What's changed:** New vitals, recent lab results, medication changes since last visit
3. **Red flags:** Abnormal values, missed appointments, overdue preventive care
4. **Context for today:** What was discussed last visit, what needs follow-up

**User Story:**

As a primary care physician reviewing 20 patient charts before clinic starts, I need a synthesized summary of what's changed and what matters for today's visit, so that I can prepare mentally for each patient in 45 seconds instead of 90 seconds, giving me 15 minutes back to review complex cases.

**Why an AI Agent is the Right Solution:**

**Not a dashboard:** A dashboard shows current vitals, current medications, current problems - but doesn't highlight *what changed*. Physician still has to compare today's BP (142/88) to last visit (138/84) manually. Agent synthesizes: "BP trending upward (138/84 → 142/88 over 3 months)."

**Not a sorted list:** "Most recent lab results" doesn't tell physician *which results matter for today*. Patient has 47 lab results; only 3 are relevant (A1C for diabetes management, creatinine for medication monitoring, lipid panel for statin therapy). Agent selects based on problem list + medication context.

**Not a better chart view:** Chronological timeline of all events (visits, labs, medications) is overwhelming. Agent provides narrative: "Patient started Lisinopril 10mg 2 weeks ago for newly diagnosed hypertension. No follow-up BP check yet. Creatinine stable at 0.9 (no medication adjustment needed)."

**Agent-specific value:**
- **Temporal reasoning:** "Last A1C was 8.2 three months ago, above target of <7.0, but patient hasn't had follow-up since."
- **Clinical synthesis:** Connects vitals + medications + labs: "BP remains elevated despite Lisinopril; may need dose increase."
- **Proactive flagging:** "Patient overdue for colorectal cancer screening (last colonoscopy 11 years ago, age 56)."

**Success Criteria:**
- Summary generated in <6 seconds
- 100% of claims have source citations (no hallucinated facts)
- Physician can formulate visit plan in 45 seconds (down from 90 seconds)
- No critical information missed (red flags surfaced: abnormal labs, medication interactions, overdue screenings)

**MVP Workflow Implementation:**

Physician clicks patient on schedule → Agent executes `pre_visit_summary` DAG:
1. Retrieve patient demographics (name, age, gender, MRN)
2. Retrieve recent vitals (last 3 visits)
3. Retrieve active medications
4. Retrieve recent lab results (last 90 days)
5. Retrieve problem list
6. Retrieve last visit note (summary only)
7. Aggregate with citations → Verify → Stream to UI

**Example Output:**

```
**John Doe, 62M - Annual Physical**

**Changed since last visit (3 months ago):**
- BP trending upward: 138/84 → 142/88 → 145/90 [source: Vitals]
- Started Lisinopril 10mg 2 weeks ago [source: MedicationRequest/m456]
- A1C stable at 6.8%, below target <7.0 [source: Observation/o789]

**Red flags:**
⚠️ BP remains elevated despite new medication (may need dose adjustment)

**Context for today:**
Last visit discussed lifestyle modifications for hypertension (reduce sodium, increase exercise). Patient scheduled for 2-week BP recheck but didn't follow up.

**Overdue screenings:**
- Colorectal cancer screening (last colonoscopy 11 years ago)
```

---

### Use Case 2: Medication Reconciliation (During Visit)

**Description:**

Patient states "I'm taking my blood pressure medicine, the white pill." Physician needs to verify which medication, dosage, frequency, and whether patient is actually taking it as prescribed. Agent cross-references patient's statement against active medications in EHR and flags discrepancies.

**User Story:**

As a physician during a patient visit, I need to verify that what the patient says they're taking matches what's in the EHR, so that I can catch medication errors (wrong dose, discontinued meds still being taken, new meds not started) before they cause harm.

**Why an AI Agent is the Right Solution:**

**Not a dashboard:** Dashboard shows "Active Medications: Lisinopril 10mg, Metformin 500mg, Atorvastatin 20mg." Patient says "I take the white pill for blood pressure, the round one for diabetes, and I stopped the cholesterol pill because it made my muscles hurt." Physician must manually map patient descriptions to medication list.

**Agent value:**
- **Natural language mapping:** Patient says "white pill for blood pressure" → Agent identifies "Likely Lisinopril 10mg (most common white BP medication)."
- **Discrepancy detection:** Patient says they stopped atorvastatin → Agent flags "Patient reports discontinuing Atorvastatin 20mg, but EHR shows active status. Verify and update."
- **Dosage verification:** Patient says "I take the diabetes pill twice a day" → Agent checks: "Metformin 500mg prescribed BID (twice daily) - matches patient report."
- **Adherence probing:** Agent suggests questions: "Ask patient: Are you taking Lisinopril every morning as prescribed?"

**Not manual chart review:** Physician would need to click Medications tab, read through list, ask patient about each one individually. With 8-12 medications (typical for elderly patient), this takes 3-5 minutes. Agent condenses to 30-second review.

**Success Criteria:**
- Medication discrepancies detected in <10 seconds
- 100% accuracy (no false positives: flagging discrepancy when none exists)
- Reduced medication errors (target: 80% reduction in "patient taking discontinued medication")

**MVP Workflow Implementation:**

Physician asks agent: "Verify patient's medications"
Agent executes `medication_review` DAG:
1. Retrieve active medications from EHR
2. For each medication: drug name, dosage, frequency, start date
3. Cross-reference against recent visit notes (patient-reported adherence)
4. Flag discrepancies:
   - Medication marked active but patient reported stopping
   - Dosage mismatch between prescribed and patient-reported
   - New prescription not yet started
5. Surface as structured list with citations

**Example Output:**

```
**Medication Reconciliation for John Doe:**

✅ **Lisinopril 10mg once daily** [source: MedicationRequest/m456]
   - Prescribed 2 weeks ago for hypertension
   - Status: Active
   - Patient should be taking: 1 tablet every morning

✅ **Metformin 500mg twice daily** [source: MedicationRequest/m123]
   - Prescribed 5 years ago for Type 2 Diabetes
   - Status: Active
   - Last refill: 25 days ago (adherent)

⚠️ **Atorvastatin 20mg once daily** [source: MedicationRequest/m789]
   - Prescribed 3 years ago for hyperlipidemia
   - Status: Active in EHR
   - **Discrepancy:** Last visit note states "Patient reports muscle aches, considering stopping statin" [source: Encounter/e999]
   - **Action needed:** Verify if patient stopped medication, update EHR status

**Recommendation:** Confirm patient is taking Lisinopril and Metformin. Discuss Atorvastatin discontinuation and document decision.
```

---

### Use Case 3: End-of-Visit Red-Flag Scan (Last 30 Seconds Before Leaving Exam Room)

**Description:**

Before ending the visit, physician asks agent: "Anything I'm missing?" Agent scans recent labs, vitals, and medications for abnormal values or potential safety issues that weren't addressed during the visit.

**User Story:**

As a physician wrapping up a visit, I need a safety net to catch critical findings I may have overlooked (abnormal lab buried in results, drug interaction with new prescription), so that I don't miss something that could harm the patient.

**Why an AI Agent is the Right Solution:**

**Not a dashboard:** Dashboards show all labs (normal and abnormal). Physician sees "47 lab results" and doesn't have time to review each one. Agent filters: "Only show abnormal values from last 90 days that weren't discussed today."

**Agent-specific value:**
- **Contextual filtering:** Agent knows what was discussed during visit (based on conversation). If physician addressed elevated A1C, agent doesn't re-flag it. But if creatinine is abnormal and wasn't mentioned, agent surfaces it.
- **Drug-drug interaction checking:** Patient prescribed new medication today (Ibuprofen for back pain). Agent checks against active medications: "⚠️ Ibuprofen + Lisinopril: Increased risk of kidney injury. Consider alternative pain medication."
- **Dosage range verification:** New prescription: "Metformin 2000mg twice daily" → Agent flags: "Dosage exceeds maximum recommended (2000mg total daily). Verify intended dose."
- **Follow-up gaps:** "Patient's A1C is 8.2 (above target). No follow-up appointment scheduled. Recommend 3-month recheck."

**Not manual checklist:** Physician could mentally run through "Did I check labs? Did I check drug interactions? Did I schedule follow-up?" But this is prone to forgetting (especially on patient #19 of the day when mental fatigue sets in). Agent automates the checklist.

**Success Criteria:**
- Scan completes in <5 seconds (minimal visit time extension)
- 95% of critical findings surfaced (high sensitivity)
- <5% false positives (abnormal values that are clinically insignificant)
- Physician acts on flagged items (orders follow-up, changes medication) in >80% of cases

**MVP Workflow Implementation:**

Physician says: "Anything I'm missing?"
Agent executes `red_flag_scan` DAG:
1. Retrieve all lab results from last visit to today
2. Filter for abnormal values (outside reference range)
3. Cross-reference against today's visit note (what was already discussed)
4. Check newly prescribed medications against active medications (drug-drug interactions)
5. Check for missing follow-up appointments for chronic conditions
6. Surface as prioritized list (critical first, minor last)

**Example Output:**

```
**Red-Flag Scan for John Doe:**

⚠️ **Critical:**
- **Creatinine 1.8 mg/dL** (reference range: 0.7-1.3) [source: Observation/o888]
  - Result from 5 days ago, not discussed today
  - **Action:** Review in context of Lisinopril (ACE inhibitors can elevate creatinine). May need renal function monitoring.

⚠️ **Moderate:**
- **Drug interaction:** Newly prescribed Ibuprofen 400mg + active Lisinopril 10mg
  - NSAIDs reduce effectiveness of ACE inhibitors and increase kidney injury risk
  - **Action:** Consider acetaminophen instead

⚠️ **Follow-up gap:**
- **A1C 6.8%** (below target, well-controlled diabetes)
  - No follow-up A1C scheduled
  - **Action:** Schedule 6-month recheck per diabetes guidelines

✅ **No other critical findings**
```

---

### Use Case 4: Free-Form Chart Q&A (Ad-Hoc During Visit)

**Description:**

During visit, physician has specific question about patient's history: "When was she last on a statin?" "Has his chest pain been evaluated?" "What was the result of the colonoscopy?" Agent searches chart and provides answer with citation.

**User Story:**

As a physician during a patient visit, I need to quickly retrieve specific historical information without interrupting workflow to manually search the chart, so that I can answer the patient's questions in real-time and make informed clinical decisions.

**Why an AI Agent is the Right Solution:**

**Not search bar:** EHR search is keyword-based. Searching "statin" returns 47 results (every mention in notes over 10 years). Physician must manually scan to find "when did patient stop taking it?"

**Agent value:**
- **Natural language query:** Physician asks "When was she last on a statin?" → Agent interprets: Search MedicationRequest for statin drug class, find most recent with status=stopped, return end date.
- **Synthesized answer:** "Patient was on Atorvastatin 20mg from 2018 to 2021. Discontinued due to muscle aches [source: MedicationRequest/m789, Encounter/e555]."
- **Temporal reasoning:** "Has his chest pain been evaluated?" → Agent searches for chest pain mentions in notes + Cardiology referrals + EKG results, synthesizes: "Chest pain first reported 6 months ago. EKG normal [source: Observation/o111]. Cardiology referral placed but patient didn't attend appointment [source: Encounter/e444]."

**Not better chart view:** Chronological timeline still requires physician to scan visually. Agent provides direct answer: "Colonoscopy performed 11 years ago, results normal [source: Procedure/p222]. Patient is overdue for repeat screening (guideline: every 10 years)."

**Success Criteria:**
- Answer provided in <8 seconds
- 100% source attribution (every claim cites original record)
- Answer accuracy: >90% (matches what physician would find with manual search)
- Handles "not found" gracefully: "No record of statin prescriptions in this chart."

**MVP Workflow Implementation:**

Physician types question into agent chat box (or uses voice input - future).
Agent executes `general_query` workflow:
1. Classify query intent (medication history, procedure history, symptom history, etc.)
2. Determine relevant FHIR resources to search (MedicationRequest, Procedure, Observation, Encounter notes)
3. Execute targeted searches with patient_id filter
4. Rank results by relevance (most recent, most specific to query)
5. Synthesize answer with citations
6. If no results found: "No record of [query subject] in this patient's chart."

**Example Queries & Responses:**

**Query:** "When was she last on a statin?"
**Response:**
```
Patient was on **Atorvastatin 20mg from March 2018 to June 2021** [source: MedicationRequest/m789].

Reason for discontinuation: Patient reported muscle aches and weakness [source: Encounter note from June 12, 2021].

No statin prescriptions since 2021.
```

**Query:** "Has his chest pain been evaluated?"
**Response:**
```
**Chest pain first reported:** January 2025 during office visit [source: Encounter/e444].

**Workup performed:**
- EKG: Normal sinus rhythm, no ST changes [source: Observation/o111]
- Troponin: <0.01 (negative) [source: Observation/o112]
- Cardiology referral placed [source: ServiceRequest/s555]

⚠️ **Patient did not attend cardiology appointment.** Last documented chest pain: February 2025 visit, described as "occasional, non-exertional" [source: Encounter/e777].
```

**Query:** "What was the colonoscopy result?"
**Response:**
```
**Colonoscopy performed:** April 2014 [source: Procedure/p222]

**Findings:** No polyps, no masses. Normal exam.

**Recommendation:** Repeat in 10 years (due April 2024).

⚠️ **Patient is overdue for repeat screening** (11 years since last colonoscopy, age 56).
```

---

### Use Case 5: Draft Visit Note (Post-Visit, 5:00-5:30 PM Documentation Time)

**Description:**

At end of day, physician has 3-4 patients with incomplete notes. For each patient, physician tells agent what happened during visit (verbal summary), and agent drafts a SOAP note structure that physician can review, edit, and approve.

**User Story:**

As a physician at end of day with 30 minutes of unpaid documentation time remaining, I need to quickly complete visit notes by verbally summarizing what happened, so that I can finish charting in 15 minutes instead of 30 and go home on time.

**Why an AI Agent is the Right Solution:**

**Not a template:** Pre-filled SOAP note templates still require physician to type out subjective (patient complaints), objective (exam findings), assessment (diagnoses), and plan (treatment). Typing 200-300 words per note × 4 patients = 1,200 words = 20-25 minutes at 50 WPM.

**Agent value:**
- **Voice-to-text + structure:** Physician says "Patient came in for annual physical. Blood pressure was 145/90. We talked about starting a low-dose ACE inhibitor. I prescribed Lisinopril 10mg once daily. Discussed lifestyle modifications. Follow-up in 2 weeks for BP recheck."
- **Agent drafts:**
  ```
  **Subjective:** Patient presents for annual physical exam.

  **Objective:**
  - BP: 145/90 mmHg [source: today's vitals]
  - [Other vitals from today]

  **Assessment:**
  - Hypertension, newly diagnosed (ICD-10: I10)

  **Plan:**
  - Started Lisinopril 10mg PO once daily for BP control
  - Discussed lifestyle modifications: reduce sodium intake, increase aerobic exercise
  - Follow-up appointment in 2 weeks for BP recheck
  - Patient education provided regarding medication adherence and side effects
  ```
- **Physician edits:** Changes "aerobic exercise" to "30 minutes walking daily", adds "patient agreeable to plan."
- **One-click approve:** Note commits to EHR with physician signature and timestamp.

**Not manual dictation:** Traditional dictation requires physician to dictate in SOAP format ("Subjective: Patient presents for..."). Agent accepts conversational summary and structures it automatically.

**Success Criteria:**
- Draft generated in <10 seconds per note
- 80% of draft content is accurate (requires minimal editing)
- Reduces documentation time from 7-8 minutes per note to 3-4 minutes per note
- Note includes all required elements (HPI, exam findings, assessment, plan, ICD-10 codes)

**MVP Workflow Implementation:**

Physician clicks patient → Opens agent → Says: "Draft visit note"
Agent prompts: "Tell me what happened during the visit"
Physician provides verbal summary (1-2 minutes of speaking)
Agent executes `draft_visit_note` DAG:
1. Retrieve today's vitals, labs ordered, medications prescribed
2. Transcribe physician's verbal summary
3. Map to SOAP structure:
   - Subjective: Patient-reported symptoms/complaints from summary
   - Objective: Vitals + exam findings from summary + today's data
   - Assessment: Diagnoses mentioned in summary, map to ICD-10 codes
   - Plan: Treatment mentioned in summary + follow-up instructions
4. Cross-reference with data (ensure vitals match what physician said)
5. Show draft to physician with inline citations
6. Physician reviews, edits, clicks "Approve"
7. Agent posts to OpenEMR as DocumentReference (FHIR write operation)

**Example Draft:**

```
**SOAP Note - John Doe - Annual Physical - 04/28/2026**

**Subjective:**
Patient presents for annual physical examination. No acute complaints. Reports occasional headaches, attributes to work stress.

**Objective:**
- Vitals: BP 145/90 mmHg, HR 78 bpm, Temp 98.4°F, Weight 185 lbs [source: Vitals from today]
- General: Well-appearing, no acute distress
- HEENT: Normocephalic, PERRLA
- CV: Regular rate and rhythm, no murmurs
- Lungs: Clear to auscultation bilaterally
- Abdomen: Soft, non-tender, non-distended

**Assessment:**
1. **Hypertension, newly diagnosed** (ICD-10: I10)
   - BP 145/90, above target <130/80 for patient's age
2. **Health maintenance**
   - Due for colorectal cancer screening (age 56)

**Plan:**
1. **Hypertension:**
   - Started Lisinopril 10mg PO once daily [source: MedicationRequest/m999 created today]
   - Discussed lifestyle modifications: reduce sodium intake to <2g/day, increase physical activity to 30 minutes daily
   - Follow-up appointment in 2 weeks for BP recheck
   - Provided patient education regarding medication adherence, potential side effects (dizziness, dry cough)

2. **Screening:**
   - Ordered colonoscopy for colorectal cancer screening (overdue, last exam 11 years ago)
   - Referred to GI (Dr. Smith's office)

3. **Follow-up:**
   - Return visit in 2 weeks for BP check
   - Patient verbalized understanding of plan and is agreeable

**Physician signature:** [Pending approval]
**Time spent:** 18 minutes
```

Physician reviews, changes "30 minutes daily" to "150 minutes per week per AHA guidelines", clicks "Approve." Note is committed to EHR.

---

## Why These Use Cases?

**Rationale for Selection:**

These five use cases were selected based on:
1. **Frequency:** Pre-visit summaries (20x/day), medication reconciliation (10-15x/day), red-flag scans (20x/day), free-form Q&A (5-10x/day), note drafting (3-4x/day) = **58-73 agent interactions per physician per day**

2. **Time savings:** Pre-visit (45 sec → 20 sec = 25 sec saved × 20 = 8 minutes/day), Med rec (3 min → 30 sec = 2.5 min saved × 12 = 30 min/day), Red-flag scan (prevents missed findings, hard to quantify time but high safety value), Free-form Q&A (2 min chart search → 8 sec agent query = 1.9 min saved × 7 = 13 min/day), Note drafting (7 min → 3 min = 4 min saved × 4 = 16 min/day). **Total: ~67 minutes saved per physician per day.**

3. **Clinical impact:** Medication reconciliation and red-flag scans directly prevent patient harm (medication errors, missed abnormal labs). Pre-visit summaries improve visit quality (physician is better prepared). Note drafting reduces physician burnout (less unpaid overtime).

4. **Agent-appropriate:** All five use cases require synthesis across multiple data sources, temporal reasoning, or natural language understanding. A dashboard or sorted list cannot solve these problems.

---

## Success Metrics

**Adoption:**
- 80% of physicians use agent for pre-visit summaries within 2 weeks of launch
- Average 50+ agent interactions per physician per day by week 4

**Time Savings:**
- Pre-clinic prep time: 20 minutes → 8 minutes (60% reduction)
- Medication reconciliation: 3 minutes → 30 seconds (83% reduction)
- End-of-day documentation: 30 minutes → 15 minutes (50% reduction)

**Safety:**
- Medication discrepancy detection: 95% sensitivity (catches 95% of discrepancies)
- Red-flag scan: 90% sensitivity (catches 90% of critical findings)
- Zero harm events attributable to agent errors (hallucinated information)

**Physician Satisfaction:**
- Net Promoter Score (NPS): >50 ("Would you recommend this agent to a colleague?")
- Burnout reduction: 30% reduction in self-reported end-of-day fatigue

**Clinical Quality:**
- Preventive care screening rates increase by 20% (agent flags overdue screenings)
- Medication adherence improves by 15% (earlier detection of non-adherence)

---

## Anti-Patterns (What We're NOT Building)

**Not a general medical Q&A chatbot:** Agent does not answer "What's the treatment for hypertension?" or "What are the side effects of Lisinopril?" Those are UpToDate/Google queries, not chart-specific questions.

**Not a diagnostic tool:** Agent does not diagnose conditions or recommend treatments. It surfaces information from the patient's chart and flags safety issues, but clinical decision-making remains with the physician.

**Not a patient-facing tool:** This is physician-only (for MVP). Future expansion to patient portal is possible, but different use cases and different safety requirements.

**Not a replacement for chart review:** Agent augments physician's review, doesn't replace it. Physician still looks at vitals, reads key notes, makes clinical decisions. Agent saves time on information retrieval and synthesis, not on clinical reasoning.
