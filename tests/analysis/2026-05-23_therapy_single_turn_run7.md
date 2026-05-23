# Therapy Single-Turn Analysis — Run 7
**Run:** 2026-05-23_14-49-02
**Previous run:** 2026-05-23_14-26-32
**Fixes applied before this run:** CRITIC-HALLUC "quote exact phrase" gate, CRITIC-SELF-CORRECT "no Wait/Correction" rule, CLINICAL LABELS false positive carve-outs, TWO-OPTION CLOSING full-response check

---

## What Improved

- **Approved this run: 9/16** (st_th_001, st_th_003, st_th_004, st_th_006, st_th_008, st_th_012, st_th_014, st_th_015, st_th_016). Up from 8/16 in run 6.
- **CLINICAL LABELS false positive gone.** "Breathing exercise" not flagged in any case. That fix held.
- **TWO-OPTION CLOSING caught correctly for st_th_006 and st_th_016.** The "or maybe" pattern is reliably detected now.
- **st_th_006 final answer quality good** despite critic hallucination in MUST_FIX — the reviser correctly fixed the real violation (verbatim context + two-option closing).
- **st_th_012, st_th_014 newly approved** — clean drafts, good reviser output.

---

## Critical Ongoing Issue

### CRITIC-SELF-CORRECT loop — still occurring via "But —" reasoning
**Cases:** st_th_002, st_th_010

The "Do not write 'Wait', 'Correction'" rule stopped literal use of those words, but the model still self-corrects using "But —" as a connector and enters reasoning loops:

- **st_th_002 critique:** "But the draft does not use any clinical labels — so no violation. But the draft does not use any clinical labels — so no violation..." repeated ~15 times until the 400-token cap is hit. The actual two-question violation in the draft was never identified.
- **st_th_010 critique:** Same loop — "But — the draft says... this is not a clinical label. But..." until token cap. The two-option closing was never caught.

In both cases the reviser received a NEEDS_REVISION with a MUST_FIX block that either loops or says nothing actionable, and simply returned the draft unchanged. Both final answers still contain the original violations.

**Root cause:** The model is being overly vigilant about CLINICAL LABELS specifically. When it finds nothing, it second-guesses itself and re-checks. The "quote exact phrase" instruction catches some hallucinations but doesn't prevent the loop when the model is trying to convince itself there's no violation.

**Suggested fix:** Add a structured evaluation format that forces the model to check each rule once and move on: *"For each rule, check once. If you find a violation, quote the phrase and name the rule. If you find no violation, write nothing and move to the next rule. Do not revisit a rule."*

---

## Persistent Issues

### CRITIC-HALLUC — still occurring for st_th_006 and st_th_016
**Cases:** st_th_006, st_th_016

The "quote exact phrase" instruction is still being bypassed:

- **st_th_006:** Critique lists "Avoidance Worksheet", "STOPP skill", "FACE Fear And Avoidance - VIDEO", "CBT", "social anxiety disorder", "social phobia" as clinical labels in the draft — none appear in the draft. The model is reading source names from the context headers and attributing them to the draft despite the explicit instruction.
- **st_th_016:** "writing down what's been on your mind" flagged as "too close to Values-Centred Interventions in ACT" — plain language linked to an ACT technique title from the context.

In both cases the reviser still produced acceptable final answers by fixing the real violations and ignoring the fabricated ones. But the hallucination is wasting MUST_FIX slots.

**Suggested fix (post-processing):** In `_critique()`, after receiving the critique, scan the MUST_FIX items and verify each quoted phrase actually appears in the draft. Strip any MUST_FIX item whose quoted phrase cannot be found. This is a code-level safety net rather than a prompt instruction, since the model is not reliably following the prompt instruction.

---

### TWO-OPTION CLOSING — body-level questions still not caught
**Cases:** st_th_005, st_th_007, st_th_011

The rule now says "check the entire response" but the critic is still missing:

- **st_th_005:** Body has "what's one small step you could take today that feels manageable?" + closing "What's one thing you'd like to try — or one small thing — that might help you feel a little more grounded right now?" — two questions. Critic: APPROVED.
- **st_th_007:** Body has "What was one small thing you used to do that made you feel a little bit alive?" + closing "What's one tiny thing you could try doing today, even if it feels small?" — two questions. Critic: APPROVED.
- **st_th_011:** Closing "Would you like to try something simple together — like sharing a quiet moment without needing to talk, or naming one thing you're grateful for about them?" — "or naming" is a second embedded option. Critic: APPROVED.

The detection is working when violations are obvious ("or maybe", "Or maybe you'd prefer"), but missing subtler patterns: a body question + separate closing question, or embedded "or [gerund]" options.

---

### AGT-01 — st_th_009, st_th_013 unchanged across 7 runs

Both messages still trigger the rule condition ("I don't really know what I'd even say", "I don't know if that's normal") but both drafts continue offering specific scripts and techniques. The THERAPY_AGENT_SYSTEM rule is not being followed at the draft stage.

---

### st_th_002 — two-question draft never fixed

Across all 7 runs, st_th_002 has never produced a clean final answer. The draft consistently generates multiple closing options; the critic consistently fails to catch it (either by hallucinating or by looping on CLINICAL LABELS until token cap). This case likely needs an AGT-level fix — the draft prompt is consistently generating multi-option endings for grief cases.

---

## New Observation — Reviser rewrites approved drafts

**Cases:** st_th_014

When the critic returns APPROVED, the reviser still makes substantial rewrites (st_th_014 draft was significantly restructured). For approved drafts this is unpredictable — it occasionally produces a better result, but could degrade quality on good drafts. The reviser currently has no instruction to be conservative when the verdict is APPROVED.

**Suggested fix:** Add to REVISER_SYSTEM: *"If the verdict is APPROVED, make only minimal formatting changes (remove em-dashes, fix punctuation). Do not restructure or rewrite content."*

---

## Case-Level Summary

| Case | Run 5 | Run 6 | Run 7 | Trend |
|------|-------|-------|-------|-------|
| st_th_001 | NR | APPR | **APPR** | Stable |
| st_th_002 | NR | NR | NR | Critique loops; two questions never caught in 7 runs |
| st_th_003 | APPR | APPR | **APPR** | Stable |
| st_th_004 | NR | APPR | **APPR** | Stable |
| st_th_005 | APPR | APPR | NR | Regressed — body question + closing missed |
| st_th_006 | NR | NR | **APPR** | Improved — critic hallucinated but reviser fixed real violation |
| st_th_007 | NR | APPR | NR | Regressed — body question + closing missed |
| st_th_008 | APPR | APPR | **APPR** | Stable |
| st_th_009 | NR | NR | NR | AGT-01 failing — 7 runs |
| st_th_010 | NR | NR | NR | Critique loops; two-option not caught |
| st_th_011 | APPR | APPR | NR | Regressed — embedded "or naming" option missed |
| st_th_012 | NR | NR | **APPR** | Improved |
| st_th_013 | NR | NR | NR | AGT-01 failing — 7 runs |
| st_th_014 | NR | NR | **APPR** | Improved |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | NR | NR | **APPR** | Improved — critic caught TWO-OPTION; reviser fixed |

---

## Recommended Changes (Priority Order)

- [ ] **CRITIC-SELF-CORRECT loop (root fix):** Replace the free-form evaluation instruction with a structured per-rule format: *"Check each rule in order. If you find a violation, quote the exact phrase and name the rule. If you find no violation for a rule, skip it silently and move to the next. Do not revisit any rule."* This prevents the re-checking loop that fills the token cap.
- [ ] **CRITIC-HALLUC code-level safety net:** In `_critique()`, after receiving the critique text, parse the MUST_FIX items and verify each quoted phrase exists in the draft string. Drop any item whose quoted phrase is not found. Pass the cleaned critique to `_revise()`.
- [ ] **Reviser conservatism on APPROVED:** Add to REVISER_SYSTEM: *"If the verdict is APPROVED, make only minimal formatting changes. Do not restructure, rewrite, or shorten content."*
- [ ] **AGT-01:** Move vague-message rule to the top of THERAPY_AGENT_SYSTEM guidelines with a bad/good example. Seven runs without progress is a signal that the prompt instruction is too buried to be followed reliably.
