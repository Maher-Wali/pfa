# Therapy Single-Turn Analysis — Run 12
**Run:** 2026-05-23_18-15-24
**Previous run:** 2026-05-23_17-52-37
**Fixes applied before this run:** `_CRITIQUE_MAX_TOKENS` 400 → 500; DISTANCING PHRASES rule — added named examples ("One thing that's helped others", "One thing that's been helpful for others"); TWO-OPTION CLOSING rule — added "Or maybe... ?" as always a second question, added embedded-option bad example.

---

## What Improved

- **13/16 approved** — same count as run 11, but different distribution.
- **st_th_014 recovered.** Was failing in run 11; clean draft and APPROVED critique this run.
- **st_th_010 reviser fixed correctly.** Critic caught the two-question structure, filter stripped a hallucinated CLINICAL LABELS bullet (not in draft), surviving TWO-OPTION bullet correctly directed reviser to drop the first two questions and keep only the closing one. Final answer clean.
- **AGT-01 still holding.** st_th_009, st_th_013, st_th_015, st_th_016 all clean.

---

## Remaining Failures

### st_th_002 — TWO-OPTION embedded "or", critic approves (12 consecutive runs)
**Persistent.**

Draft: "Would you like to try something small — like writing a letter to your dad, or making a space in your day where you can just sit and cry without judgment? Or maybe you'd prefer to sit with a cup of tea and let yourself feel the weight of the silence — that's enough, too."

The first question contains embedded options ("writing a letter... or making a space"). The "Or maybe" clause ends with a period, not a question mark — so our new rule ("a sentence beginning with 'Or maybe' and ending with '?' is always a second question") does not fire. The critic approved.

The embedded "or" between two options inside a single question still escapes detection. The new TWO-OPTION rule example added this run did not change the critic's behaviour for this specific pattern.

**Root cause:** The draft's first question itself presents two embedded options without a second question mark anywhere. Our rule targets (a) two "?" and (b) embedded "or" — but the critic is not applying (b) reliably when both options are inside a single "Would you like to try X or Y?" structure.

**Suggested fix (prompt):** Make the embedded-option violation explicit with an exact structural match: "If the closing question presents two things the user could try ('Would you like to try X, or Y?', 'like writing X, or making a space for Y?'), that is a violation even if only one '?' appears." Add this as a named bad example.

---

### st_th_004 — REVISER-LOOP with meta-commentary (new failure)
**Regression from run 11.**

Draft has three questions ("Would you like to try...?", "Or would you prefer to try...?", "What's been sitting...?") — a genuine NEEDS_REVISION case. But the critic output a verbose internal reasoning block inside the MUST_FIX section:

```
MUST_FIX:

Actually, let's recheck:

- "Would you like to try...?" — this is a single question.
- "Or would you prefer to try...?" — this is a second question — violation.
...
So:
- Rule 6: Three questions — violation.
- Rule 7: "Ahhh" — verbatim — violation.

But rule 6 is more severe...

VERDICT: NEEDS_REVISION
MUST_FIX:
- TWO-OPTION CLOSING — ...
- TWO-O   [truncated]
```

The critique contains three VERDICT: NEEDS_REVISION lines and reasoning text ("Actually, let's recheck:", "So:", "But rule 6 is more severe") mixed with the bullets. `_filter_hallucinated_must_fix` partitions on the first "MUST_FIX:" and cannot clean reasoning prose from the block. The reviser received this messy critique and entered a reasoning loop, explicitly outputting its verification attempts in the final answer:

> "...What's been sitting with you the most lately?, No, that's still three questions. Let me fix this. [...] Still three questions. I need to merge..."

The final_answer contains multiple attempts and explicit meta-commentary — the opposite of what REVISER_SYSTEM instructs.

**Root cause (two interacting causes):**
1. The critic is still producing verbose step-by-step reasoning inside the MUST_FIX block despite the "correct once and move on" instruction. The 500-token increase gave it more room to do so.
2. The REVISER_SYSTEM instruction "Before returning your answer, silently verify: for each MUST_FIX item, confirm the violation is no longer present" is being executed non-silently — the model outputs the verification loop verbatim.

**Suggested fixes:**
- **Code-level:** In `_filter_hallucinated_must_fix`, after partitioning, strip non-bullet non-empty lines from the MUST_FIX block (remove "Actually, let's recheck:", "So:", etc. — any line not starting with "-" and not empty). This prevents reasoning prose from reaching the reviser.
- **Prompt (reviser):** Remove "Before returning your answer, silently verify..." — this instruction is the direct cause of the output loop. The reviser already has "Do not argue with or comment on the critique" — the verify instruction contradicts it by prompting internal reasoning.
- **Prompt (critic):** Add explicit instruction: "After writing your evaluation, output ONLY the final VERDICT block — no 'Actually', 'So:', 'But —', or any intermediate reasoning text after the verdict line."

---

### st_th_005 — CRITIC-HALLUC masks real TWO-OPTION (ongoing)
**Different failure mode from run 11.**

Draft has two questions: "Would you like to try something small today that might help you feel grounded?" and "What's been sitting with you the most lately?" — a genuine TWO-OPTION CLOSING violation.

Critic output: hallucinated CLINICAL LABELS ("DBT Skills for Your New Year's Celebrations", "Intermediate Coping Strategies by Lisa Dietz") from RAG context headers — neither appears in the draft. The critic never reached a TWO-OPTION assessment. After hallucinated bullets were stripped by the filter (correctly — the quoted phrases are not in the draft), no surviving MUST_FIX items remained → critique converted to APPROVED. Reviser made minimal changes. Two-question structure survived to the final answer.

**Root cause:** The SCOPE instruction ("find the exact phrase from the DRAFT ANSWER — if you cannot find it verbatim, do not flag it") is not consistently preventing clinical label hallucination. The critic is lifting labels from RAG context headers and flagging them as if they appear in the draft. The hallucination consumed the critic's budget before it evaluated rule 6.

**Suggested fix (prompt):** Before the CLINICAL LABELS rule, add: "IMPORTANT — check the DRAFT ANSWER text, not the Retrieved Context headers. The context headers begin with 'Technique:' — those labels belong to the source, not the draft. Do not flag them."

---

## Case-Level Summary

| Case | Run 10 | Run 11 | Run 12 | Trend |
|------|--------|--------|--------|-------|
| st_th_001 | APPR* | APPR | **APPR** | Stable |
| st_th_002 | NR | NR | NR | Embedded "or" — 12 runs |
| st_th_003 | APPR | APPR | **APPR** | Stable |
| st_th_004 | NR | APPR | NR | Regression — REVISER-LOOP |
| st_th_005 | NR | NR | NR | Critic-halluc masks TWO-OPTION |
| st_th_006 | APPR | APPR | **APPR** | Stable |
| st_th_007 | APPR | APPR | **APPR** | Stable |
| st_th_008 | APPR | APPR | **APPR** | Stable |
| st_th_009 | NR | APPR | **APPR** | Stable — AGT-01 holding |
| st_th_010 | APPR | APPR | **APPR** | Stable |
| st_th_011 | APPR | APPR | **APPR** | Stable |
| st_th_012 | APPR | APPR | **APPR** | Stable |
| st_th_013 | NR | APPR | **APPR** | Stable |
| st_th_014 | APPR | NR | **APPR** | Recovered |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | APPR | APPR | **APPR** | Stable |

---

## Recommended Changes (Priority Order)

- [ ] **REVISER-LOOP — remove "silently verify" (prompt):** Delete the "Before returning your answer, silently verify..." instruction from REVISER_SYSTEM. It causes the model to output its verification loop explicitly. The "Do not argue with or comment on the critique" rule already covers this.
- [ ] **Critic reasoning prose in MUST_FIX (code):** In `_filter_hallucinated_must_fix`, after partitioning on "MUST_FIX:", strip any non-bullet non-empty lines (lines not starting with "-"). Removes "Actually, let's recheck:", "So:", "But —" prose from the block before it reaches the reviser.
- [ ] **st_th_005 CRITIC-HALLUC (prompt):** Before the CLINICAL LABELS rule, add: "IMPORTANT — check the DRAFT ANSWER text only. The Retrieved Context headers begin with 'Technique:' — those labels belong to the source documents, not the draft. Do not flag them."
- [ ] **st_th_002 embedded-option (prompt):** Add to TWO-OPTION CLOSING rule: "A closing question that offers two things to try inside a single sentence ('Would you like to try writing X, or making a space for Y?') is a violation even if only one '?' appears."
