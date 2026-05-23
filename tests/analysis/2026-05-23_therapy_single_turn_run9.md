# Therapy Single-Turn Analysis — Run 9
**Run:** 2026-05-23_15-59-18
**Previous run:** 2026-05-23_15-21-37
**Fixes applied before this run:** CRITIC-FORMAT "write NOTHING for clean rules", CLINICAL LABELS carve-outs ("grounding exercise", "thought exercise", "journaling"), CRITIC one-verdict constraint, `_resolve_dual_verdict()` code, `_quote_matches_draft()` ellipsis handling

---

## What Improved

- **st_th_010 fixed.** Was producing a broken fragment in run 8 ("Or maybe you'd prefer..."); now has a coherent single-question ending. The dual-verdict fix and ellipsis filter both contributed.
- **st_th_014 preserved closing question.** In run 8 the reviser dropped the closing question from an APPROVED draft. This run it was kept — reviser conservatism is holding for this case.
- **st_th_006 CLINICAL LABELS hallucination stripped.** "CBT", "social anxiety disorder", "fear of being scrutinized" were all fabricated by the critic; the filter correctly removed them and converted to APPROVED.
- **st_th_010 ellipsis filter working.** The filter correctly kept the TWO-OPTION CLOSING item (fragments "Would you like to try something simple" and "Or maybe you'd prefer" both found in draft) and stripped the hallucinated CLINICAL LABELS item (neither source name appeared in draft).

---

## Approved this run: 10/16

(st_th_003, st_th_004, st_th_006, st_th_007, st_th_008, st_th_010*, st_th_012, st_th_014, st_th_015, st_th_016)

*st_th_010 borderline — final question "What would feel manageable right now, whether it's sitting quietly with your feeling, or checking what's in your fridge..." embeds two options with "or", but is a single grammatical question. Treated as clarifying "or" exception.

Down from 11/16 in run 8. Net losses: st_th_005, st_th_011, st_th_013 (gained st_th_010, st_th_014).

---

## Ongoing Critical Issues

### CRITIC-LOOP — morphed from "But —" to "But wait —"
**Cases:** st_th_002, st_th_011

The "write NOTHING for clean rules" instruction stopped the critic from outputting separate bullet items for clean rules, but did not prevent looping within a single bullet item. The CLINICAL LABELS check now generates one long bullet that self-corrects internally:

- **st_th_002:** Single MUST_FIX bullet: "The draft does not contain any clinical labels. So this rule is not violated. But wait — the draft does not contain any clinical labels. So this rule is not violated. But wait — the draft does not contain any clinical labels..." repeated until token cap. The real violation (TWO-OPTION CLOSING with "or maybe you'd prefer") was never identified.
- **st_th_011:** Same pattern: "The draft does not name any clinical labels. So this rule is not violated. The draft does not name any clinical labels..." Token cap reached on CLINICAL LABELS. Two-question violation in the draft never caught.

In both cases the reviser received a looping MUST_FIX item pointing to a false CLINICAL LABELS violation. The reviser couldn't fix it and returned the draft largely unchanged. Both finals have the original violations.

**Root cause:** The model is stuck in a confirmation loop on CLINICAL LABELS specifically. "But wait" is the new surface form of the same reasoning pattern as "But —". The instruction change affected the output structure (one bullet vs many) but not the underlying re-checking behaviour.

**Suggested fix (prompt-level):** Add to CRITIC_SYSTEM after the evaluation method: *"Forbidden phrases — never write these words in your evaluation: 'but wait', 'however the draft', 'but the draft does not', 'wait', 'correction'. If you begin to second-guess a finding, stop. Your first assessment of each rule is final."*

**Suggested fix (code-level):** After receiving the raw critique, detect repetition in any MUST_FIX bullet: if a 6-word span repeats 3+ times within a bullet item, that bullet is a loop — strip it entirely.

---

### BUG-01 resurface — st_th_001
**Case:** st_th_001

The reviser appended a `*Note:*` meta-commentary block to the final answer:
> "...What feels most doable for you right now?, *Note: The draft has been revised to remove clinical labels and avoid two embedded options. "4-7-8 breathing technique" is now described in plain language, and "ground yourself right now" is rephrased to avoid implying a named technique. The structure avoids "or" between two options, even though the question is phrased as an open-ended choice.*"

This violates the REVISER_SYSTEM instruction "Do not argue with, comment on, or add notes about the critique." The instruction is still not preventing the model from appending asterisk-delimited notes.

Also note: the reviser failed to actually fix the TWO-OPTION CLOSING. The final answer still has "Or maybe you'd prefer to talk to your manager or HR" + "What feels most doable for you right now?" — three question/option clauses.

**Suggested fix:** Strengthen the no-notes instruction in REVISER_SYSTEM: *"Never append an asterisk note, parenthetical, or any sentence describing what you changed. The output must be the revised answer only — no description, no justification, no trailing commentary of any kind."*

---

### DISTANCING PHRASE reviser fail — st_th_005
**Case:** st_th_005

The critic correctly flagged "One thing that's helped others in similar situations" as a DISTANCING PHRASES (Rule 3) violation. The reviser changed it to "One idea that's helped some people" — which is semantically identical framing. The reviser replaced one distancing phrase with another.

**Suggested fix:** Add to REVISER_SYSTEM: *"If flagged for DISTANCING PHRASES, do not rephrase 'helped others' into 'helped some people' or any equivalent. Remove the framing entirely and rewrite as a direct suggestion starting with 'Try', 'You could', or similar."*

---

### Post-processor gap — two questions separated by non-question sentence
**Case:** st_th_011

The draft contained: "Would you like to try something simple: take five minutes to notice what's really happening right now, without judgment? Just observe your thoughts, your body, your breath, that's enough to start grounding yourself. What's been sitting with you the most lately?"

`_strip_double_closing_question` checks whether the last two non-empty lines both end with "?". Here the second-to-last non-empty line ends with "." (the "Just observe..." sentence), so the condition is not met. The two questions passed through post-processing uncaught.

**Suggested fix (code-level):** In `_strip_double_closing_question`, also count "?" in the full text of the final paragraph. If there are 2+ "?" in any paragraph, apply the sentence-level stripping (already exists for this). The current sentence-level pass only runs on the final paragraph; the issue here is that both questions are in the final paragraph, separated by a non-question sentence. Verify the sentence-level logic handles this case.

---

## Persistent Issues

### AGT-01 — st_th_009 (9 consecutive runs), st_th_013 regression
- **st_th_009:** Input: "I don't really know what I'd even say." Draft offers concrete scripts ("I've been thinking about things lately"). 9 consecutive runs with no improvement. This is a draft-level pattern that prompt instructions are not fixing.
- **st_th_013:** Clean in run 8; reverted to offering exercises ("write down one of the thoughts... Or, if you're up for it, we could try a short, gentle exercise") this run. Inconsistent draft behaviour depending on run. The AGT-01 rule is not being consistently applied even when it worked in the previous run.

---

## Case-Level Summary

| Case | Run 7 | Run 8 | Run 9 | Trend |
|------|-------|-------|-------|-------|
| st_th_001 | NR | NR | NR | Critic halluc stripped, but TWO-OPTION + BUG-01 in final |
| st_th_002 | NR | NR | NR | Critic loop ("But wait") — 9 runs |
| st_th_003 | APPR | APPR | **APPR** | Stable |
| st_th_004 | APPR | APPR | **APPR** | Stable |
| st_th_005 | NR | APPR | NR | Regressed — distancing phrase, reviser swapped for equivalent |
| st_th_006 | APPR | APPR | **APPR** | Stable |
| st_th_007 | APPR | APPR | **APPR** | Stable |
| st_th_008 | APPR | APPR | **APPR** | Stable |
| st_th_009 | NR | NR | NR | AGT-01 — 9 runs |
| st_th_010 | NR | NR | **APPR*** | Improved — ellipsis filter + dual-verdict fix |
| st_th_011 | NR | APPR | NR | Regressed — critic loop, two questions not caught |
| st_th_012 | APPR | APPR | **APPR** | Stable |
| st_th_013 | NR | APPR | NR | Regressed — AGT-01 not consistent |
| st_th_014 | APPR | APPR* | **APPR** | Stable — reviser now preserves closing question |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | APPR | APPR | **APPR** | Stable |

---

## Recommended Changes (Priority Order)

- [ ] **CRITIC-LOOP — forbidden phrases:** Add to CRITIC_SYSTEM: *"Forbidden self-correction phrases — never write: 'but wait', 'however the draft', 'but the draft does not', 'wait —', 'correction'. If you begin to re-examine a rule you already assessed, stop immediately and move to the next rule."*
- [ ] **CRITIC-LOOP — code-level repetition detection:** In `_critique()`, after receiving the raw critique, detect if any MUST_FIX bullet contains a repeated 6-word span 3+ times. If so, strip that bullet (it is a reasoning loop, not a real finding). Adjust verdict if no bullets survive.
- [ ] **REVISER no-notes:** Strengthen REVISER_SYSTEM: *"Never append an asterisk note, parenthetical, or any sentence describing what you changed. Output only the revised answer — nothing else."*
- [ ] **REVISER distancing phrase fix:** Add to REVISER_SYSTEM: *"If flagged for DISTANCING PHRASES, do not rephrase as 'helped some people' or any equivalent. Remove the distancing framing entirely and rewrite as a direct first-person suggestion: 'Try X' or 'You could X'."*
- [ ] **Post-processor — sentence-level two-question detection:** In `_strip_double_closing_question`, verify the sentence-level paragraph pass correctly handles two "?" sentences separated by a non-question sentence. Ensure it strips all but the last question sentence in any final paragraph with 2+ questions.
- [ ] **AGT-01 — code-level safety net:** After generating the draft, check if the input matches the vague-message pattern (two sentences or fewer, or explicit trigger phrases). If matched, strip the draft down to validation sentences (no "?" endings) plus only the last question sentence. This is a post-processing pass on the draft before it reaches the critic.
