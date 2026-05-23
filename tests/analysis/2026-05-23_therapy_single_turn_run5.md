# Therapy Single-Turn Analysis — Run 5
**Run:** 2026-05-23_14-09-20
**Previous run:** 2026-05-23_13-52-44
**Fixes applied before this run:** CRITIC-ALL — added inline "or maybe" example to TWO-OPTION CLOSING rule

---

## What Improved

- **TWO-OPTION CLOSING now being caught** — st_th_004, st_th_012, st_th_013 all received NEEDS_REVISION for "or maybe" patterns. The rule addition worked for detection.
- **st_th_008 APPROVED** — clean breathing exercise, single closing question, no violations.
- **st_th_015, st_th_016 APPROVED** — consistent, no regression.
- **st_th_014 APPROVED** — philosophical case, consistently clean.

---

## Regressions

**Approved this run: 5/16** (st_th_003, st_th_008, st_th_014, st_th_015, st_th_016). Down from 10/16 in run 4. The critic change caused regressions on previously-clean cases.

---

## Critical New Issues

### REV-LOOP-2 — Reviser fills token cap with self-arguing text instead of revising
**Cases:** st_th_004, st_th_013

When the critic returns a contradictory NEEDS_REVISION critique, the reviser argues with it instead of revising, and fills its 600-token budget with repetitive garbage:

- **st_th_004**: Final answer = unchanged draft + ~500 tokens of "This is not a violation. The two-option closing is not present. The draft does not present two distinct actions as choices." repeated 30+ times.
- **st_th_013**: Final answer = two sentences of content (one repeated) + original closing question KEPT unchanged + hundreds of trailing commas until token cap.

This is the run 3 loop pattern in a new form. The reviser is not revising — it is processing a confused MUST_FIX list, getting stuck, and filling tokens with self-argumentation.

**Root cause:** The critic self-corrected mid-critique for both cases (see CRITIC-SELF-CORRECT below), producing a MUST_FIX list that is internally contradictory. The reviser reads "MUST_FIX: [item]... Wait — correction: that is NOT a violation" and cannot reconcile it.

**Suggested fix (reviser):** Add to REVISER_SYSTEM: "Do not argue with, comment on, or analyze the critique. Do not add any notes or explanations. Output only the revised answer. If the critique contradicts itself, fix only the clearly stated violations and ignore the rest."

**Suggested fix (critic):** Add to CRITIC_SYSTEM: "Do not revise or contradict your own analysis mid-response. Do not write 'Wait', 'Correction', or 'Let me recheck'. State each finding once, finalize it, and move on."

---

### CRITIC-HALLUC — Critic fabricates clinical label violations from RAG context
**Cases:** st_th_006, st_th_010, st_th_011

The critic is reading the source metadata in the Retrieved Context (which contains "DBT", "CBT", "trauma-focused CBT") and attributing those labels to the draft — even when the draft contains none of them:

- **st_th_010**: Critique flags "refers to 'emotional regulation DBT skill' and 'DBT class'" — neither phrase appears anywhere in the draft.
- **st_th_011**: Critique flags "references 'DBT skills' and 'Coping with Depression'" — not in the draft.
- **st_th_006**: Critique flags "references social anxiety disorder and social phobia" — not in the draft.

These false positives triggered NEEDS_REVISION on cases that were previously correctly APPROVED in run 4. For st_th_010 and st_th_002, the reviser then leaked a meta-note into the final answer (BUG-01 resurface).

**Root cause:** The critic prompt receives the Retrieved Context alongside the draft. The model conflates source labels in the context with claims made in the draft.

**Suggested fix:** Add an explicit scope instruction to CRITIC_SYSTEM before the rules: "You are evaluating the DRAFT ANSWER only. The Retrieved Context is provided for reference but contains source metadata (technique names, modality labels) that belong to the sources, not to the draft. Do not flag clinical labels that appear only in the Retrieved Context headers — only flag terms that appear in the DRAFT ANSWER itself."

---

### CRITIC-SELF-CORRECT — Critic contradicts itself mid-critique
**Cases:** st_th_004, st_th_006, st_th_010

The critic writes MUST_FIX items, then immediately retracts them in the same response:

- **st_th_006**: "DISTANCING PHRASES: 'I hear how much this is weighing on you'... Wait — correction: The draft does not violate Rule 3 or Rule 6."
- **st_th_004**: Lists VERBATIM CONTEXT as a violation, then "this is not a violation... Rule 7 is not violated."
- **st_th_010**: Flags DBT labels, then pivots: "the reference to 'DBT' and 'emotional regulation' is a violation" (which itself doesn't appear in the draft).

Self-correction within the critique confuses the reviser, which tries to process contradictory MUST_FIX items and generates garbage output (see REV-LOOP-2).

---

### BUG-01 resurface — Reviser appends meta-notes to final answer
**Cases:** st_th_002, st_th_010

The reviser is leaking cleanup notes into the final answer:

- **st_th_002**: Final answer ends with `*, *Note: This response has been revised to remove the clinical label "grief therapy" and to avoid presenting two options...`
- **st_th_010**: Final answer ends with `*, *Note: This response avoids clinical terminology and does not mimic the phrasing of the retrieved context verbatim.*`

The REVISER_SYSTEM already says "Return only the final improved answer — no preamble, no meta-commentary, no critique text." The instruction is being ignored when the reviser is confused.

**Suggested fix:** Add post-processing in `_revise()` / `respond()` to strip any content beginning with `*Note:`, `Note:`, or `* Note` from the output. This is a safety net, not a substitute for fixing the root cause.

---

## Persistent Issues

### CRITIC-MISSED — Critic not catching double questions in response body
**Cases:** st_th_001, st_th_007

Both drafts contain a question in the body followed by a separate closing question. The critic approved both.

- **st_th_001**: "What's one small thing you could try right now...?" (body) + "What's one small step you'd like to try first, if you're ready?" (close)
- **st_th_007**: "What if we start small — like noticing one thing..." (body) + "What's one small thing you could try doing...?" (close)

Two questions in one response reads as interrogating the user. The critic is only checking the closing sentence/paragraph, not the full response.

**Suggested fix:** Add to CRITIC_SYSTEM rule 6: "Also flag if the response contains more than one question anywhere — a question mid-response followed by a closing question counts as a two-question violation."

---

### AGT-01 — Still not working for st_th_009
**Case:** st_th_009

Input contains "I don't really know what I'd even say" — an AGT-01 trigger phrase. The draft still offered a specific script ("you could try writing a short note or email... 'I've been thinking about things lately, and I'd like to talk if you're open to it'"). The reviser then made it MORE prescriptive in the final answer.

---

## Case-Level Summary

| Case | Run 3 | Run 4 | Run 5 | Trend |
|------|-------|-------|-------|-------|
| st_th_001 | NR | NR | NR | Double question persists |
| st_th_002 | NR | NR | NR | Reviser leaked meta-note; closing still broken |
| st_th_003 | NR | APPR | APPR | Stable |
| st_th_004 | NR | NR | NR | REV-LOOP-2 — garbage output |
| st_th_005 | NR | APPR | APPR | Stable |
| st_th_006 | NR | APPR | NR | Regressed — critic hallucinated labels |
| st_th_007 | NR | APPR | NR | Regressed — double question, critic missed |
| st_th_008 | NR | NR | **APPR** | Improved |
| st_th_009 | NR | NR | NR | AGT-01 still failing |
| st_th_010 | NR | APPR | NR | Regressed — critic hallucinated labels |
| st_th_011 | APPR | APPR | NR | Regressed — critic hallucinated labels |
| st_th_012 | NR | APPR | NR | Critic correctly flagged TWO-OPTION; final answer missing closing question |
| st_th_013 | NR | NR | NR | REV-LOOP-2 — commas filling token cap |
| st_th_014 | APPR | APPR | **APPR** | Stable |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | NR | APPR | **APPR** | Stable |

---

## Recommended Changes (Priority Order)

- [ ] **CRITIC-HALLUC (root cause)**: Add scope instruction to CRITIC_SYSTEM before all rules: *"Evaluate the DRAFT ANSWER only. The Retrieved Context headers contain technique/modality labels that belong to the sources. Do not flag a term as a clinical label unless it appears in the DRAFT ANSWER itself."*
- [ ] **CRITIC-SELF-CORRECT**: Add to CRITIC_SYSTEM: *"Do not write 'Wait', 'Correction', or mid-stream revisions. State each finding once. Do not retract or contradict earlier findings within the same response."*
- [ ] **REV-LOOP-2 (reviser)**: Add to REVISER_SYSTEM: *"Do not argue with, comment on, or analyze the critique. If the critique appears contradictory, fix only the clearly stated violations and ignore the rest. Never add notes or explanations."*
- [ ] **BUG-01 safety net**: Strip any trailing `*Note:` / `Note:` block from the reviser output in `_revise()` before returning.
- [ ] **CRITIC-MISSED body questions**: Add to CRITIC_SYSTEM rule 6: *"Also flag responses that contain more than one question total — a question in the body followed by a closing question is a violation."*
