# Therapy Single-Turn Analysis — Run 11
**Run:** 2026-05-23_17-52-37
**Previous run:** 2026-05-23_17-29-10
**Fixes applied before this run:** Added "no violation" / "not a violation" / "so no violation" phrase check to `_filter_hallucinated_must_fix()` — strips CRITIC-FORMAT bullets where the critic's own text concludes the rule passes.

---

## What Improved

- **Approved this run: 13/16** — best result across all 11 runs. Up from 12/16 in run 10.
- **CRITIC-FORMAT fully resolved.** "No violation" bullets are stripped before reaching the reviser. No cases where the reviser over-corrected due to phantom MUST_FIX items.
- **st_th_009 clean for the first time in 11 runs.** AGT-01 rule at the top of THERAPY_AGENT_SYSTEM with a bad/good example finally produced the correct behaviour: vague message → single open question, no technique or script.
- **st_th_013 also clean.** AGT-01 compliance held for the second consecutive case this run.
- **st_th_014 recovered.** Previously flagged for "or" between two options — draft clean this run.

---

## Remaining Failures

### st_th_002 — TWO-OPTION CLOSING, critic approves (11 consecutive runs)
**Persistent issue.**

Draft: "Would you like to try something small — like writing a letter to your dad, or sitting with the memory of him in a quiet space? Or maybe just letting yourself sit in the silence?"

TWO-OPTION CLOSING is present ("Would you like to try... or sitting...", plus "Or maybe"). Critic wrote VERDICT: APPROVED — the violation was not caught.

**Root cause:** The critic is not detecting the embedded "or" within a single question as a two-option closing. The rule as written may be interpreted as requiring two separate question sentences, not a single question with two embedded alternatives. The draft consistently generates grief-topic closings with "or maybe" and the critic consistently passes them.

**Suggested fix (prompt):** Make the TWO-OPTION rule explicit about embedded alternatives: "A single question that presents two embedded options ('try X or Y?', 'would you like to try X, or maybe Y?') is also a violation." Add a bad example with an embedded "or maybe".

---

### st_th_005 — DISTANCING PHRASE survives to final answer (multiple runs)
**Input:** "I've been trying to meditate but I keep getting distracted..."

Critique hit the 400-token cap mid-sentence on the DISTANCING PHRASE bullet (truncated before concluding whether "One thing that's been helpful for others" is a violation). Reviser changed "non-negotiable boundary" to "personal ritual" but left "One thing that's been helpful for others" untouched in the final answer.

**Root cause:** Token cap truncation prevents the critic from delivering a complete, actionable MUST_FIX bullet for the distancing phrase. Reviser receives an incomplete signal and skips the fix.

**Suggested fix (code):** Raise `_CRITIQUE_MAX_TOKENS` from 400 to 500. The loop fix eliminated the token-waste from repetition — 400 is now tight when there are 2–3 genuine violations to articulate. 500 would give the critic room to complete all bullets without truncation.

**Alternative fix (prompt):** Add "One thing that's helped others" and "One thing that's been helpful for others" as explicit examples in the DISTANCING PHRASES rule.

---

## Case-Level Summary

| Case | Run 9 | Run 10 | Run 11 | Trend |
|------|-------|--------|--------|-------|
| st_th_001 | NR | APPR* | **APPR** | Stable |
| st_th_002 | NR | NR | NR | TWO-OPTION embedded "or" — 11 runs |
| st_th_003 | APPR | APPR | **APPR** | Stable |
| st_th_004 | APPR | NR | **APPR** | Recovered — CRITIC-FORMAT fix removed phantom bullets |
| st_th_005 | NR | APPR | NR | Critic token-truncated — distancing phrase survives |
| st_th_006 | APPR | APPR | **APPR** | Stable |
| st_th_007 | APPR | APPR | **APPR** | Stable |
| st_th_008 | APPR | APPR | **APPR** | Stable |
| st_th_009 | NR | NR | **APPR** | FIRST CLEAN — AGT-01 finally working |
| st_th_010 | APPR* | APPR | **APPR** | Stable |
| st_th_011 | APPR | APPR | **APPR** | Stable |
| st_th_012 | APPR | APPR | **APPR** | Stable |
| st_th_013 | NR | NR | **APPR** | Improved — AGT-01 compliance held |
| st_th_014 | APPR | APPR | **APPR** | Stable |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | APPR | APPR | **APPR** | Stable |

---

## Recommended Changes (Priority Order)

- [ ] **st_th_005 / token truncation (code):** Raise `_CRITIQUE_MAX_TOKENS` from 400 to 500. The critic loop fix makes 400 sufficient for simple cases but too tight when 2–3 genuine violations need full articulation.
- [ ] **st_th_002 / embedded two-option (prompt):** Extend the TWO-OPTION CLOSING rule in CRITIC_SYSTEM to explicitly cover single questions with embedded alternatives ("Would you like to try X, or maybe Y?" is a violation). Add a bad example of this pattern.
- [ ] **st_th_005 / distancing phrase (prompt):** Add "One thing that's been helpful for others" and "One thing that's helped others" as named examples in the DISTANCING PHRASES rule, so the critic flags them even without a complete bullet.
