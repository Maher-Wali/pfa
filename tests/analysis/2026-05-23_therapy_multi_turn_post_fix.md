# Therapy Agent — Multi-Turn Suite Analysis (Post-Fix Run)
**Run:** `2026-05-23_19-57-10`  
**Suite:** `therapy_multi_turn`  
**Conversations:** 3 | **Total turns:** 12  
**Baseline run for comparison:** `2026-05-23_19-21-24`

---

## Summary

The two new critic rules (Rule 9 — Unanswered Direct Question, Rule 10 — Repeated Closing Pattern) produced partial wins but introduced three new problems: a dramatic latency increase, critic verbosity/hallucination on clean rules, and a reviser that over-strips APPROVED drafts. Latency roughly doubled relative to the baseline. Rule 10 caught one genuine closing repetition and the reviser fixed it; Rule 9 fired once correctly but missed two of its intended targets. The underlying draft quality issue — the model generating "One thing that's helped others" — was not solved by the critique changes and needs to be addressed at the draft level.

---

## Latency Comparison

| | Baseline run | Post-fix run | Change |
|---|---|---|---|
| Min | 28.8s | 39.5s | +10.7s |
| Max | 61.7s | 127.0s | +65.3s |
| Median | ~41s | ~100s | ~+59s |
| NEEDS_REVISION turns | 2/12 | 8/12 | +6 |

The latency increase is explained by more NEEDS_REVISION verdicts (each adds a full revision LLM call). Eight turns now require revision vs two before, which is a regression from a user-experience standpoint even if some of those revisions are legitimate.

---

## Per-Rule Performance

### Rule 9 — Unanswered Direct Question

**Fired correctly once:** mt_th_001 turn 3 — *"How do I actually say no without feeling guilty?"* The critic flagged this, and the reviser removed the distancing phrase that was masking the pivot. Partial credit: the final answer still ends with a generic closing question rather than a direct answer, so the reviser addressed the wrong part of the flag.

**Missed mt_th_002 turn 4:** *"How do people get through this?"* — direct question, dual-verdict resolved to APPROVED, Rule 9 never ran. The final answer pivots to an exercise without first answering the question — the same failure mode identified in the baseline analysis.

**Missed mt_th_003 turn 4:** *"What do I do when the anxiety hits at work in front of other people?"* — direct question with a specific constraint (public, at a desk). The critique spent its budget listing clinical labels not present in the draft and never reached Rule 9. Final answer again offers a sensory-noticing exercise that the user just said wouldn't work in this context.

### Rule 10 — Repeated Closing Pattern

**Fired correctly once:** mt_th_001 turn 2 — closing *"What's one small boundary..."* matched the structure of turn 1's *"What's one small thing..."*. The reviser changed it to *"What's one small step..."*, which is a genuine, if minor, improvement.

**Missed mt_th_002 turns 3 and 4:** Both end with *"What's the one thing you've been carrying..."* — a verbatim structural repeat. Turn 3's critique self-corrected to APPROVED via dual-verdict before Rule 10 could act.

**Missed mt_th_003 turns 3 and 4:** Turn 3 ends *"What's one small movement or sensation..."*, turn 4 ends *"What's one small thing you can notice or do..."* — same opener. Turn 3 dual-verdict resolved to APPROVED; turn 4's critique malformed before reaching Rule 10.

---

## New Problems Introduced

### 1. Critic verbosity on clean rules (violates critic's own instructions)

The critic is instructed: *"If you find no violation: write NOTHING."* In this run it violated that in multiple turns, writing out every rule with an explicit "not used" or "no violation" note. From mt_th_002 turn 2:

> *"REPEATED QUESTION — The draft asks... this is a single question. No repeated question."*
> *"REDUNDANT SUGGESTION — The draft suggests... this is not redundant with anything the user said."*

This inflates critique length toward the 500-token budget and crowds out the rules that matter. The mt_th_003 turn 4 critique is the worst offender — it lists all six clinical label examples with "— not used" next to each, consuming most of the budget before reaching Rules 9 or 10.

### 2. Dual-verdict self-correction masking real violations

Three turns show `VERDICT: NEEDS_REVISION\nVERDICT: APPROVED` (mt_th_002 turns 3-4, mt_th_003 turn 3). `_resolve_dual_verdict` keeps the last verdict (APPROVED), which is correct when the critic caught its own hallucination — but in these turns the self-correction dismisses legitimate Rule 10 catches. The pattern suggests the critic detects a violation, writes it, then second-guesses itself because it cannot find the exact quoted phrase (satisfying `_filter_hallucinated_must_fix`'s verbatim check). Rule 10 operates on structural similarity, not verbatim quotes, which makes it incompatible with the existing hallucination filter.

### 3. Reviser over-strips APPROVED drafts

mt_th_003 turn 2 (APPROVED verdict):  
- **Draft:** Warm two-paragraph response with acknowledgment, a specific breathing + noticing exercise, and a closing question.  
- **Final:** *"Take three slow, deep breaths... You're not trying to fix anything. You're just noticing."* — two sentences, no acknowledgment, no closing question.

The REVISER_SYSTEM says *"make only minimal formatting changes"* on APPROVED, but the reviser removed the entire opening paragraph and the closing question. This is a reviser prompt compliance failure that strips therapeutic value even from passing drafts.

### 4. Malformed critique in mt_th_001 turn 4

The MUST_FIX section for turn 4 is corrupted: it repeats items, includes inline reasoning mid-bullet, and ends mid-sentence (*"CLINICAL LABELS — "Setting Healthy Boundaries""*). This looks like the critique hit its 500-token ceiling (`_CRITIQUE_MAX_TOKENS`) mid-generation, leaving a truncated and unparseable MUST_FIX list. The reviser still ran and produced a reasonable final answer, but the critique metadata stored in the DB is misleading.

---

## Persistent Draft-Level Issue

The phrase **"One thing that's helped others"** appears in the drafts of mt_th_001 turns 1, 2, 3, 4 and mt_th_002 turn 2 — five of twelve turns. The draft system prompt already prohibits this directly (*"Do not frame suggestions as things 'that have helped others'. Offer them directly and personally."*), but the model repeatedly generates it. The critique correctly flags it as a DISTANCING PHRASES violation in most of these turns, but that means every turn with this phrase now requires a revision pass, adding ~20-30s each.

The instruction exists but it is buried in a list of 14 guidelines. It is not in the **hard constraints** block and has no BAD/GOOD example to anchor the behaviour. This is better addressed at draft generation time than caught by the critique.

---

## What Improved vs the Baseline

| | Baseline | Post-fix |
|---|---|---|
| Rule 10 catches formulaic closing | 0/12 | 1/12 (partial) |
| Rule 9 catches unanswered question | 0/12 | 1/12 (partial) |
| "One thing that's helped others" caught | inconsistent | consistently flagged |
| NEEDS_REVISION turns | 2/12 | 8/12 |
| Latency average | ~41s | ~100s |
| Critic hallucination volume | low | high |

---

## Recommendations

### High priority

**Move "One thing that's helped others" into the hard constraints block.**  
The draft system prompt already prohibits distancing phrases, but the rule is buried in a 14-item guideline list with no example. The model ignores it five out of twelve turns. Move it next to the hard formatting constraints and add a BAD/GOOD example in the same style as the vague-message rule — that pattern demonstrably works elsewhere in the prompt.

**Fix critic verbosity before anything else.**  
The critic is writing out a "no violation" note for every clean rule, consuming the 500-token budget before reaching Rules 9 and 10. The existing instruction says "write NOTHING for clean rules" but the model ignores it. Reword it more forcefully: *"Move on silently. Do not write the rule name. Do not write 'no violation'. Do not explain why it passed. Silence is the only correct output for a rule with no violation."* This is the most impactful change because it directly unblocks Rules 9 and 10 from being crowded out.

**Redesign Rule 10 to work with the hallucination filter.**  
Rule 10 asks the critic to detect structural similarity, but `_filter_hallucinated_must_fix` requires a verbatim quote from the draft. Structural matches never produce verbatim quotes, so the filter strips the finding and the verdict flips to APPROVED — which explains all three dual-verdict cases in this run. Two options: (1) ask the critic to emit a separate yes/no structural-similarity check *before* the VERDICT block, outside the MUST_FIX format, so the filter doesn't touch it; or (2) move closing-pattern detection entirely out of the critique and into `_draft()`, where the `asked_questions` list already exists — extend it to also pass the closing sentence of `last_assistant` as a structural pattern to avoid, and let the drafter handle it before critique runs.

### Medium priority

**Tighten the REVISER_SYSTEM instruction for APPROVED verdicts.**  
The reviser deleted an entire opening paragraph and a closing question from an APPROVED draft (mt_th_003 turn 2). Add an explicit constraint: *"On APPROVED: do not remove any sentence. Do not remove the closing question. Do not remove the opening acknowledgment. Fix only punctuation and em-dashes."*

**Raise `_CRITIQUE_MAX_TOKENS` from 500 to 700.**  
With 10 rules, the critique now regularly hits the token ceiling mid-generation, leaving truncated and unparseable MUST_FIX lists. 700 tokens gives enough headroom without meaningfully increasing cost per turn.

### Low priority

**Investigate `_filter_hallucinated_must_fix` interaction with the dual-verdict pattern.**  
Three turns self-corrected from NEEDS_REVISION to APPROVED. In at least two of those cases a real violation (Rule 10) was likely pruned because it lacked a verbatim quote. Once Rule 10 is redesigned (see above), check whether the dual-verdict rate drops — if it does, the filter is the cause and may need a carve-out for structural-similarity rules.
