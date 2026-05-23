# Therapy Single-Turn Analysis — Run 4
**Run:** 2026-05-23_13-52-44
**Previous run:** 2026-05-23_13-17-36
**Fixes applied before this run:** CRIT-01 (reviser token cap 600), CRT-01 root fix (removed rules 1 & 3 from critic entirely), REV-01 (MUST_FIX cap 2 items), AGT-01 (explicit trigger phrases), BUG-02 sentence-level strip

---

## What Improved

- **CRIT-01 fully resolved.** st_th_016 elapsed 33.1s (was 165s in run 3). No reviser loop anywhere. Reviser token cap is working.
- **CRT-01 root fix — no more false EMOTION PROJECTION flags.** Removing rules 1 and 3 from the critic eliminated the entire class of false positives that plagued runs 1–3.
- **No profile contamination.** Clean baseline maintained.
- **st_th_016 APPROVED** — "You're not being dramatic, you're just being human. And that's enough to matter." + single clean question. Strong improvement over previous runs.
- **st_th_015 APPROVED** (again) — AGT-01 working for "I don't know how else to put it". No suggestions offered.
- **New approvals: st_th_003, st_th_005, st_th_006, st_th_007, st_th_010, st_th_011, st_th_012, st_th_014.** These were NR in run 3.
- **All 16 cases completed** in 22.8s–39.4s. No errors, no loops.

---

## Critical New Issue

### CRITIC-ALL — Critic approved all 16 cases, including cases with clear violations

Every critique in this run returned `VERDICT: APPROVED`. This is overcorrection. Removing rules 1 and 3, combined with the 2-item MUST_FIX cap, made the critic too permissive — it rubber-stamped responses containing violations it previously caught correctly (like TWO-OPTION CLOSING).

Cases where the critic should NOT have approved:

- **st_th_004** — final answer ends with "Would you like to try a short guided breathing or relaxation exercise together, or maybe we can look at a few simple thoughts to gently challenge the ones that feel like they're keeping you awake?" — two embedded options, should fail TWO-OPTION CLOSING (rule 6).
- **st_th_008** — final answer ends with "Want to try it for a few minutes, or adjust the pace or try something else?" — same violation.
- **st_th_009** — offered a specific script ("I've been feeling a bit overwhelmed lately") to a message that contains the AGT-01 trigger phrase "I don't really know what I'd even say." Should have asked one question only.
- **st_th_013** — offered a technique (write down the thought, read it out loud) despite the trigger phrase "I don't know if that's normal." Should have asked one question only.

The TWO-OPTION CLOSING rule is defined in the critic, but the model is failing to recognize the inline "or maybe" pattern as two options. The rule needs a concrete example of what an inline two-option sentence looks like.

**Suggested fix:** Add a concrete negative example to the TWO-OPTION CLOSING rule in CRITIC_SYSTEM: *"A question containing 'or maybe' is also two options, even in one sentence — e.g. 'Would you like to try X, or maybe we could Y?' must be flagged."*

---

## Persistent Issues

### AGT-01 — Trigger phrases active but draft still offers techniques

**Cases:** st_th_009, st_th_013

The new trigger phrases were added in this run but the model continues to offer suggestions:

- **st_th_009** ("I don't really know what I'd even say"): Draft offers a script — "you could begin with something simple — like 'I've been feeling a bit overwhelmed lately, and I wanted to talk about it'" — and also suggests writing a note. This is advice, not a question. The final answer retains these.
- **st_th_013** ("I don't know if that's normal"): Draft offers a specific technique — "you could try writing down the thought — even if it feels weird — and then read it out loud or look at it in a mirror." This is directly in violation of the AGT-01 rule.

The trigger phrases are recognised at a conceptual level (AGT-01 is working for st_th_015), but the model is not consistently applying the "one question only, no technique" constraint. The rule may be buried too deep in the guideline list.

**Suggested fix:** Move the vague-message rule to the top of the Guidelines section in THERAPY_AGENT_SYSTEM, above all other guidelines, and add a concrete bad example: *"BAD: 'You could try writing down what you're feeling.' GOOD: 'What's the first thing that comes up when you sit with this feeling?'"*

---

### BUG-02 — Sentence-level strip produces awkward output

**Case:** st_th_002

The draft for st_th_002 ended with three sentences in one paragraph: a two-part option question, a second question ("Or maybe you'd prefer to just sit with the silence?"), and "I'm here to listen, no matter what."

The new sentence-level strip kept the last question and moved the non-question before it:

> "I'm here to listen, no matter what. Or maybe you'd prefer to just sit with the silence for a few minutes?"

The "Or maybe" prefix is now disconnected — it reads as if continuing a thought that no longer exists. The fix is mechanically correct (one question) but produces unnatural text.

**Suggested fix:** When the sentence-level strip selects the last question sentence, also strip any leading connector words ("Or maybe", "Or", "And maybe") from the start of that sentence before placing it at the end.

---

### DRAFT-ORPHAN — st_th_001 final answer has disconnected sentence

**Case:** st_th_001

The draft suggested a breathing exercise with: "Would you like to try something simple first — like focusing on your breathing for just a few minutes while you're sitting at your desk? You can do it quietly, without anyone noticing."

The reviser removed the breathing suggestion but kept the consequence: the final answer contains "You can do it quietly, without anyone noticing." with no referent — the thing being done quietly was removed.

This is a reviser consistency problem. When the reviser removes a suggestion, it should also remove dependent sentences.

This is hard to fix systematically. It will self-resolve as critic + reviser quality improves. No immediate fix recommended.

---

## Case-Level Summary

| Case | Run 1 | Run 2 | Run 3 | Run 4 | Trend |
|------|-------|-------|-------|-------|-------|
| st_th_001 | NR | NR | NR | NR | Orphaned sentence; draft quality reasonable |
| st_th_002 | APPR | NR | NR | NR | Strip fix produced awkward ending |
| st_th_003 | NR | NR | NR | **APPR** | Improved — clean, focused |
| st_th_004 | NR | NR | NR | NR | Two-option closing persists, critic missed it |
| st_th_005 | NR | NR | NR | **APPR** | Improved |
| st_th_006 | NR | NR | NR | **APPR** | Good |
| st_th_007 | NR | NR | NR | **APPR** | Good |
| st_th_008 | APPR | NR | NR | NR | Two-option closing persists, critic missed it |
| st_th_009 | NR | NR | NR | NR | AGT-01 trigger present, script offered anyway |
| st_th_010 | NR | NR | NR | **APPR** | Acceptable; 3-sentence message, AGT-01 doesn't trigger |
| st_th_011 | NR | APPR | NR | **APPR** | Consistent good quality |
| st_th_012 | NR | NR | NR | **APPR** | Improved significantly |
| st_th_013 | NR | NR | NR | NR | AGT-01 trigger phrase present, technique offered |
| st_th_014 | APPR | NR | APPR | **APPR** | Consistently good |
| st_th_015 | NR | NR | APPR | **APPR** | Consistent, AGT-01 working |
| st_th_016 | NR | NR | NR | **APPR** | Major improvement — 33s vs 165s, strong response |

**Approved this run:** st_th_003, st_th_005, st_th_006, st_th_007, st_th_010, st_th_011, st_th_012, st_th_014, st_th_015, st_th_016 — **10/16**

---

## Recommended Changes (Priority Order)

- [ ] **CRITIC-ALL**: Add inline two-option example to TWO-OPTION CLOSING rule in CRITIC_SYSTEM: *"This includes single-sentence questions with 'or maybe': 'Would you like to try X, or maybe we could Y?' is two options and must be flagged."*
- [ ] **AGT-01**: Move the vague-message rule to the top of the Guidelines section in THERAPY_AGENT_SYSTEM. Add a bad/good example pair inline so the model has a concrete pattern to match against.
- [ ] **BUG-02 strip connector**: When the sentence-level strip selects the final question, remove leading connector words ("Or maybe", "Or ", "And maybe") from its start before returning.
