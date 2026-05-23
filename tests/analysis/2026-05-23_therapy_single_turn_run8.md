# Therapy Single-Turn Analysis — Run 8
**Run:** 2026-05-23_15-21-37
**Previous run:** 2026-05-23_14-49-02
**Fixes applied before this run:** CRITIC-SELF-CORRECT structured evaluation method, CRITIC-HALLUC code-level filter (`_filter_hallucinated_must_fix`), REVISER APPROVED conservatism, AGT-01 moved to top of THERAPY_AGENT_SYSTEM with bad/good example

---

## What Improved

- **Approved this run: 11/16** (st_th_003, st_th_004, st_th_005, st_th_006, st_th_007, st_th_008, st_th_011, st_th_012, st_th_013, st_th_015, st_th_016). Up from 9/16 in run 7. (+st_th_014 is borderline — see below.)
- **CRITIC-SELF-CORRECT loop resolved.** No more 400-token repetition loops ("But — the draft says... But —"). The structured evaluation format eliminated that pattern.
- **st_th_013 newly approved** — AGT-01 now working for intrusive thoughts case. For 7 consecutive runs this failed; the rule-at-top fix worked here.
- **st_th_005, st_th_007, st_th_011 newly approved.** Clean drafts, critic approved correctly.
- **st_th_006 hallucination gone.** No "STOPP skill", "CBT", "social anxiety disorder" in MUST_FIX. Scope instruction + filter combo is holding.

---

## New Issues This Run

### CRITIC-FORMAT — Critic outputs all rule evaluations as MUST_FIX bullet items
**Cases:** st_th_001

The structured evaluation method ("move on silently if no violation") is not being followed. Instead of listing only violations, the critic outputs ALL rule evaluations as bullet items under MUST_FIX, including "this is fine" statements:

```
MUST_FIX:
- CLINICAL LABELS: "grounding exercise" — violation
- CLINICAL LABELS: "thought exercise" — violation
- TWO-OPTION CLOSING: ... — violation
- REDUNDANT SUGGESTION: ... borderline ... not the top priority.
- VERBATIM CONTEXT: The draft does not copy verbatim — this is fine.
- PROFILE RECITATION: No user profile facts are quoted — this is fine.
- REPEATED QUESTION: No repeated question — this is fine.
- LENGTH: The draft is 5 sentences — this is fine.
```

The "this is fine" items survive `_filter_hallucinated_must_fix` because they contain no quoted phrase (unverifiable → kept by default). The reviser receives a polluted MUST_FIX block and produces a confused output that introduces new violations.

**Root cause:** The model interprets "write rule name and move on silently" as "write all rule names with a status". The instruction "do not write anything" needs to be more explicit.

**Suggested fix:** Replace "If you find no violation, move on silently" with: "If you find no violation for a rule, write NOTHING — not a rule name, not 'no violation', not 'this is fine'. The only output allowed is violation findings."

---

### FILTER FALSE NEGATIVE — Critic quotes with ellipsis, filter removes legitimate violations
**Cases:** st_th_001

The critic quoted the TWO-OPTION CLOSING violation as:
```
"Would you like to try... or maybe you'd prefer..."
```
The `...` substitutions mean this string does not appear verbatim in the draft, so `_filter_hallucinated_must_fix` strips the item. The TWO-OPTION violation is removed from MUST_FIX and never fixed by the reviser.

**Suggested fix (code-level):** Before checking if the quoted phrase appears in the draft, strip `...` and surrounding whitespace from both the quoted phrase and the draft match attempt. Or use a partial-match strategy: if the quoted phrase contains `...`, split on it and check if all non-ellipsis fragments appear in the draft.

---

### DUAL VERDICT self-correction — st_th_010
**Case:** st_th_010

The CRITIC-SELF-CORRECT fix stopped "But —" loops but the model found a new way to self-correct: writing two competing verdict lines:
```
VERDICT: NEEDS_REVISION
VERDICT: APPROVED
```
No MUST_FIX block was present. `_filter_hallucinated_must_fix` returns the string unchanged (no "MUST_FIX:" present). The reviser received both verdicts and half-acted on NEEDS_REVISION: it stripped the first option from the two-option closing but left `"Or maybe you'd prefer to reach out to someone you trust..."` as a standalone sentence fragment:

> "I hear how quiet and heavy that feeling can feel... Or maybe you'd prefer to reach out to someone you trust, even if it feels small right now?"

The final answer is broken.

**Suggested fix (code-level):** In `_critique()`, after receiving the raw critique, detect if both verdicts are present. If so, take the last verdict as authoritative (the model's correction). Strip the earlier verdict line.

**Suggested fix (prompt-level):** Add to CRITIC_SYSTEM: "Once you write a VERDICT line, do not write another. Your first VERDICT is final."

---

## Persistent Issues

### AGT-01 — st_th_009 unchanged across 8 runs
**Case:** st_th_009

Input: "A friend suggested I try talking to someone. I don't really know what I'd even say."
Trigger: "I don't really know what I'd even say" is an explicit example in the rule.

Draft still offers multiple scripts ("I've been feeling really heavy lately") and techniques (write a letter/text). The critic approves it. The rule being at the top of THERAPY_AGENT_SYSTEM helped st_th_013 but not st_th_009 — the phrasing difference may matter ("don't really know what I'd even say" vs "I don't know if that's normal").

Eight consecutive runs with no progress. This may need an agent-level or post-processing intervention rather than a prompt instruction.

---

### TWO-OPTION CLOSING — st_th_002 approved with "or maybe" violation
**Case:** st_th_002

The draft closes with: "Would you like to try writing down what you're feeling right now... or maybe find a quiet moment to sit with your thoughts..."

"or maybe" is the exact trigger pattern the critic should catch under rule 6. The critic returned APPROVED. This case has never produced a clean final in 8 runs. The draft consistently ends with multi-option closings for grief cases.

This is likely a draft-level tendency rather than a critic failure. The grief prompt elicits "gentle options" phrasing from the model repeatedly.

---

### CLINICAL LABELS false positives — "grounding exercise", "thought exercise"
**Case:** st_th_001

The critic flagged:
- `"grounding exercise"` — not in the explicit clinical labels list (which has "grounding technique"). Plain language.
- `"thought exercise"` — not a clinical technique name at all. Plain language.

Both phrases exist in the draft, so `_filter_hallucinated_must_fix` keeps them. The reviser spends its budget on these false positives and produces a worse answer.

**Suggested fix:** Add to the CLINICAL LABELS rule carve-outs: "grounding exercise", "thought exercise", "journaling", "noticing" are NOT clinical labels. Only flag specific named programme labels (e.g. "grounding technique", "cognitive restructuring", "EMDR") or specific named skill acronyms (e.g. "Distract with ACCEPTS", "PLEASE skill", "TIPP skill").

---

### REVISER still rewrites APPROVED drafts — st_th_014
**Case:** st_th_014

Critic returned APPROVED. The reviser removed the closing question "What's been sitting with you the most lately?" from the draft entirely, producing a different ending. The APPROVED conservatism instruction reduced major rewrites but the reviser is still making substantive edits.

The quality of the final answer is acceptable, but the instruction "make only minimal formatting changes" is not being followed strictly.

---

## Case-Level Summary

| Case | Run 6 | Run 7 | Run 8 | Trend |
|------|-------|-------|-------|-------|
| st_th_001 | APPR | APPR | **NR** | Regressed — critic format issue; false clinical label + TWO-OPTION filtered out |
| st_th_002 | NR | NR | NR | "or maybe" approved again — draft-level grief pattern |
| st_th_003 | APPR | APPR | **APPR** | Stable |
| st_th_004 | APPR | APPR | **APPR** | Stable |
| st_th_005 | APPR | NR | **APPR** | Improved — TWO-OPTION caught and fixed |
| st_th_006 | NR | APPR | **APPR** | Stable — hallucination gone |
| st_th_007 | APPR | NR | **APPR** | Improved |
| st_th_008 | APPR | APPR | **APPR** | Stable |
| st_th_009 | NR | NR | NR | AGT-01 failing — 8 runs |
| st_th_010 | NR | NR | NR | Dual verdict; reviser produces fragment |
| st_th_011 | APPR | NR | **APPR** | Improved |
| st_th_012 | NR | APPR | **APPR** | Stable |
| st_th_013 | NR | NR | **APPR** | Improved — AGT-01 now working for this case |
| st_th_014 | NR | APPR | APPR* | Borderline — reviser drops closing question from APPROVED draft |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | NR | APPR | **APPR** | Stable |

---

## Recommended Changes (Priority Order)

- [ ] **CRITIC-FORMAT:** Add to CRITIC_SYSTEM evaluation method: *"If you find no violation for a rule, write NOTHING — not a rule name, not 'no violation', not 'this is fine'. Only output lines for rules where you found an actual violation. Silence is correct for clean rules."*
- [ ] **CLINICAL LABELS false positives:** Add carve-outs to rule 2: *"Also NOT violations: 'grounding exercise', 'thought exercise', 'journaling'. Plain English descriptions of activities are never clinical labels — only named programme techniques (e.g. 'grounding technique', 'EMDR', 'cognitive restructuring') or skill acronyms (e.g. 'Distract with ACCEPTS', 'PLEASE skill')."*
- [ ] **FILTER — ellipsis quotes:** In `_filter_hallucinated_must_fix`, when a quoted phrase contains `...`, split on `...` and check that all non-ellipsis fragments (≥4 chars) appear in the draft. Keep the item only if all fragments match.
- [ ] **DUAL VERDICT — code-level:** In `_critique()`, after receiving the raw critique, if both `VERDICT: NEEDS_REVISION` and `VERDICT: APPROVED` are present, take the last one as authoritative. Strip the first verdict line before passing to the reviser.
- [ ] **CRITIC-SYSTEM — one verdict:** Add to CRITIC_SYSTEM: *"Once you write a VERDICT line, do not write another. Your first VERDICT is final."*
- [ ] **st_th_002 / st_th_009:** These likely need draft-level or post-processing fixes. st_th_002 repeatedly generates multi-option grief closings; st_th_009 AGT-01 has failed 8 runs. Consider a post-processing pass on the draft that counts questions and strips all but the last before the critic sees it.
