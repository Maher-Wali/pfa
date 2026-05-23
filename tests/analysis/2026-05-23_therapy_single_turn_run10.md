# Therapy Single-Turn Analysis — Run 10
**Run:** 2026-05-23_17-29-10
**Previous run:** 2026-05-23_15-59-18
**Fixes applied before this run:** `_is_looping_bullet()` repetition detector in filter, prompt "correct once and move on" (replaced forbidden-phrases instruction)

---

## What Improved

- **Approved this run: 12/16** — best result across all 10 runs. Up from 10/16 in run 9.
- **CRITIC-LOOP mostly resolved.** No full "But wait" repetition loops detected in any case. The combination of prompt instruction and code-level detection has eliminated the token-cap-consuming loops.
- **st_th_005 newly clean** — DISTANCING PHRASE correctly caught AND reviser correctly rewrote "One thing that's helped others" as a direct "Try imagining yourself..." suggestion. First time the full catch-and-fix cycle worked for this case.
- **st_th_010, st_th_011, st_th_012 all stable/improved** — clean drafts, APPROVED critic, minimal reviser changes.

---

## Remaining Failures

### st_th_002 — dual verdict, reviser produces fragment
**Persistent issue (10 runs)**

Draft: "Would you like to try something small — like writing a letter to your dad, or sitting with the memory of him in a quiet space? Or maybe just letting yourself sit in the silence?"
TWO-OPTION CLOSING present. Critic wrote "VERDICT: NEEDS_REVISION\nVERDICT: APPROVED" — dual verdict.

`_resolve_dual_verdict` correctly took the last (APPROVED). Reviser received only "VERDICT: APPROVED" as critique and should have made minimal changes. Instead it stripped "Would you like to try something small..." entirely and left only:

> "Or maybe just letting yourself sit in the silence, without trying to "fix" anything?"

— a dangling sentence fragment with no context.

**Root cause:** The reviser is still making substantive structural changes on APPROVED critiques, despite the "minimal formatting changes only" instruction. This is a recurring pattern for st_th_002 specifically — the grief draft consistently generates a multi-option close, the critic self-corrects to APPROVED, and the reviser strips content.

**Suggested fix (code-level):** When `_resolve_dual_verdict` converts a NEEDS_REVISION to APPROVED (i.e., the earlier verdict was NEEDS_REVISION), flag this as a "self-corrected" critique. Pass this to `_revise()` with an explicit marker so the reviser knows it should only strip em-dashes.

---

### st_th_004 — CRITIC-FORMAT + reviser over-correction
**Case:** st_th_004

Critic still output ALL rules as MUST_FIX bullet items, including rules it assessed as clean:

```
- CLINICAL LABELS — "jotting down a few thoughts"... not clinical labels, so this is not a violation... Wait — the draft does not name any clinical labels. So no violation here.
- DISTANCING PHRASES — "You're not alone in this"... not a distancing phrase... Not a violation.
- TWO-OPTION CLOSING — two questions: "Would you like to try..." and "What's been sitting..." — violation.
- VERBATIM CONTEXT — No verbatim... no violation.
```

The filter could not strip the false bullets because each contains a quoted phrase that exists verbatim in the draft. The reviser received four MUST_FIX bullets, three of which explicitly conclude "no violation" or "not a violation."

The reviser over-corrected: it stripped the entire empathy/validation section and returned only:
> "Would you like to try jotting down a few thoughts that pop up at night...?"

No opening, no validation, no warmth — just a bare technique question. The response is technically answerable but feels cold and incomplete.

**Root cause:** The filter keeps bullets that have quoted phrases in the draft, even when the bullet text explicitly concludes "no violation." The reviser then treats all four bullets as actionable and over-fixes.

**Suggested fix (code-level):** In `_filter_hallucinated_must_fix`, after checking for loops and quotes, also strip any bullet item whose text contains "no violation", "not a violation", or "so no violation here" — these are the critic's own conclusion that the rule passes, and they should never reach the reviser.

---

### st_th_009 — AGT-01 (10 consecutive runs)
Input: "I don't really know what I'd even say."

Draft offers: scripts ("thinking about what's been sitting with you"), writing a note, "Or, if you're nervous". Nine complete sentences. Critic APPROVED. The rule has never been followed for this case in 10 runs.

---

### st_th_013 — AGT-01 inconsistent
Input: "I don't know if that's normal."

Draft offers: "try writing down one of the thoughts... read it out loud... Or, if you're feeling stuck, you might try letting yourself feel the thought without trying to push it away." Two exercises with "Or" between them. Critic APPROVED.

Was clean in run 8 (draft produced only validation + one question), failed in runs 9 and 10 (draft offered exercises). AGT-01 compliance is stochastic — depends on the draft.

---

## Case-Level Summary

| Case | Run 8 | Run 9 | Run 10 | Trend |
|------|-------|-------|--------|-------|
| st_th_001 | NR | NR | APPR* | Improved — critic semi-looped but reviser produced clean output |
| st_th_002 | NR | NR | NR | Dual verdict → APPROVED → reviser fragment — 10 runs |
| st_th_003 | APPR | APPR | **APPR** | Stable |
| st_th_004 | APPR | APPR | NR | Regressed — CRITIC-FORMAT + reviser over-corrected |
| st_th_005 | NR | NR | **APPR** | Improved — distancing phrase caught and correctly rewritten |
| st_th_006 | APPR | APPR | **APPR** | Stable |
| st_th_007 | APPR | APPR | **APPR** | Stable |
| st_th_008 | APPR | APPR | **APPR** | Stable |
| st_th_009 | NR | NR | NR | AGT-01 — 10 runs |
| st_th_010 | APPR* | APPR* | **APPR** | Stable |
| st_th_011 | NR | APPR | **APPR** | Stable |
| st_th_012 | APPR | APPR | **APPR** | Stable |
| st_th_013 | APPR | NR | NR | AGT-01 inconsistent — draft-dependent |
| st_th_014 | APPR | APPR | **APPR** | Stable |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | APPR | APPR | **APPR** | Stable |

---

## Recommended Changes (Priority Order)

- [ ] **CRITIC-FORMAT — strip "no violation" bullets (code):** In `_filter_hallucinated_must_fix`, after the loop and quote checks, add: if the bullet text contains `"no violation"`, `"not a violation"`, or `"so no violation"` (case-insensitive), strip the bullet. This removes the critic's own clean-rule assessments before they reach the reviser.
- [ ] **st_th_002 / reviser fragment (code):** When `_resolve_dual_verdict` discards a NEEDS_REVISION in favour of a later APPROVED, pass only `"VERDICT: APPROVED"` (already done) but also strip any remaining MUST_FIX content that may have been partially generated. Currently the reviser sometimes strips the wrong content when it sees a sparse APPROVED critique after a long NEEDS_REVISION header.
- [ ] **AGT-01 (code-level safety net):** After generating the draft, check if the input matches the vague-message pattern. If matched, run a post-process that strips all content except validation sentences and the last question sentence.
