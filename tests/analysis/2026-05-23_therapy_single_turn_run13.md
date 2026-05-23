# Therapy Single-Turn Analysis — Run 13
**Run:** 2026-05-23_18-47-12
**Previous run:** 2026-05-23_18-15-24
**Fixes applied before this run:** Non-empty non-bullet lines stripped from MUST_FIX block in `_filter_hallucinated_must_fix` (removes "Actually, let's recheck:", "So:", "Note:" prose before it reaches the reviser).

---

## What Improved

- **15/16 approved** — best result across all 13 runs. Up from 13/16 in run 12.
- **st_th_004 recovered.** REVISER-LOOP fully gone — the draft generated a clean single-question structure this time, and the non-bullet stripping would have protected against the prose pollution even if it hadn't.
- **st_th_005 clean for the first time.** Draft produced a focused response with one technique and one question — no distancing phrase, no two-question structure.
- **st_th_002 structurally improved** (see below — borderline, not fully resolved, but meaningfully different from 12 prior runs).
- **st_th_003 distancing phrase caught and fixed.** Draft generated "One thing that's helped others is talking about what's really bothering you" — newly named example in the DISTANCING PHRASES rule. Critic flagged it, reviser stripped it. First time the full catch-and-fix cycle worked for a distancing phrase in this case.

---

## Remaining Failures

### st_th_009 — AGT-01 (stochastic — failed this run)
Input: "A friend suggested I try talking to someone. I don't really know what I'd even say."

The phrase "I don't really know what I'd even say" matches the AGT-01 trigger verbatim. Draft offered scripts ("I've been feeling a bit stuck lately, and I wanted to talk about it") and suggestions (write a note or message first, write down one thing to share with a friend) — clear AGT-01 violations.

Critic: VERDICT: APPROVED — the critic has no AGT-01 rule and cannot catch this.

**Root cause:** AGT-01 is entirely drafter-side. When the draft violates it, there is no catch-and-fix path. The rule held in runs 11–12 stochastically; it failed here without any code or prompt change.

**Suggested fix (critic):** Add an AGT-01 rule to CRITIC_SYSTEM so violations can be detected and fixed. Something like: "SHORT/VAGUE MESSAGE — If the user's message is two sentences or fewer and signals uncertainty about where to begin (e.g. 'I don't really know', 'I don't know what I'd even say', 'I'm not sure where to start'), the draft must not offer techniques, scripts, suggestions, or exercises. It must ask exactly one open question. Flag if it does anything else."

---

### st_th_002 — Embedded-or in closing question (improved but borderline)
**Persistent underlying issue — structurally better this run.**

Draft: "Would you like to try something small today — like walking for 10 minutes, or writing down one thing you're feeling right now — even if it's just 'I miss him' or 'I'm tired' — and then put it down?"

One "?" only — no second "Or maybe?" sentence. This is the first time in 13 runs the draft did not generate a second question mark. The new TWO-OPTION rule ("A sentence beginning with 'Or maybe' and ending with '?' is always a second question") appears to have suppressed the "Or maybe..." continuation.

However, the closing question still presents two embedded options inside a single sentence ("walking for 10 minutes, or writing down one thing"). The critic correctly approved this by current rules. The intent of the rule is to prevent two-option closings, but our rule only fires on two "?" or on an "Or maybe...?" sentence — it does not yet cover embedded "or" within a single question.

**Suggested fix (prompt):** Apply the fix recommended after run 12: "A closing question that offers two things to try inside a single sentence ('Would you like to try writing X, or Y?') is a violation even if only one '?' appears. Offer one option, not two."

---

## Case-Level Summary

| Case | Run 11 | Run 12 | Run 13 | Trend |
|------|--------|--------|--------|-------|
| st_th_001 | APPR | APPR | **APPR** | Stable |
| st_th_002 | NR | NR | APPR* | Improved — single "?", embedded-or remains |
| st_th_003 | APPR | APPR | **APPR** | Stable — distancing phrase caught and fixed this run |
| st_th_004 | APPR | NR | **APPR** | Recovered — REVISER-LOOP resolved |
| st_th_005 | NR | NR | **APPR** | First time clean |
| st_th_006 | APPR | APPR | **APPR** | Stable |
| st_th_007 | APPR | APPR | **APPR** | Stable |
| st_th_008 | APPR | APPR | **APPR** | Stable |
| st_th_009 | APPR | APPR | NR | AGT-01 stochastic — drafter-only rule |
| st_th_010 | APPR | APPR | **APPR** | Stable |
| st_th_011 | APPR | APPR | **APPR** | Stable |
| st_th_012 | APPR | APPR | **APPR** | Stable |
| st_th_013 | APPR | APPR | **APPR** | Stable |
| st_th_014 | NR | APPR | **APPR** | Stable |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | APPR | APPR | **APPR** | Stable |

---

## Recommended Changes (Priority Order)

- [ ] **AGT-01 in critic (prompt):** Add rule to CRITIC_SYSTEM: "SHORT/VAGUE MESSAGE — If the user's message is two sentences or fewer and contains a phrase signalling uncertainty about where to begin ('I don't really know', 'I don't know what I'd even say', 'I'm not sure where to start', 'I don't know how to put it'), the draft must not offer techniques, scripts, suggestions, or exercises — ask exactly one open question only. Flag any draft that offers anything else for this input type."
- [ ] **st_th_002 embedded-or (prompt):** Add to TWO-OPTION CLOSING rule: "A closing question that offers two things to try inside a single sentence ('Would you like to try walking, or writing something down?') is a violation even if only one '?' appears. Offer one option, not two."
- [ ] **CRITIC-HALLUC scope note (prompt):** Add before CLINICAL LABELS rule: "IMPORTANT — evaluate the DRAFT ANSWER text only. The Retrieved Context headers begin with 'Technique:' — those labels belong to the source documents, not the draft. Do not flag them." (Preventive — not triggered this run but recurs across multiple runs.)
