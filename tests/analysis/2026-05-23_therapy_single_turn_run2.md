# Therapy Single-Turn Analysis — Run 2
**Run:** 2026-05-23_12-51-47
**Cases:** 16
**Previous run:** 2026-05-23_11-08-11
**Fixes applied before this run:** BUG-02, REV-01, CRT-01, CRT-02, AGT-01, AGT-02

---

## What Improved

- **CRT-02 (token cap) — fully working.** The critique is now capped and the reasoning loops are gone. st_th_004 went from 154.7s to 51.9s. st_th_013 went from 154.3s to 62.1s. No more "Wait — the draft does not say..." spirals.
- **CRT-01 (classification step) — partially working.** The critic now correctly labels the user message at the top of every critique (DISTRESSED / AMBIGUOUS / POSITIVE). This is visible in every case and the reasoning is cleaner.
- **BUG-02 (double closing questions) — fixed for the line-separated case.** st_th_016, which triggered the bug in run 1, now ends with a single question. The line-by-line strip is working.
- **AGT-02 (varied closing question) — measurable improvement.** Several cases now end with contextually specific questions: "What's one small thing you've noticed that's helped you feel a little more steady?" (st_th_011), "What's been showing up for you lately?" (st_th_016). Generic "What feels right for you right now?" is less dominant.
- **st_th_011 (caretaker fatigue) — APPROVED, strong response.** Contextually accurate, no profile injection, appropriate tone.
- **st_th_014 (philosophical) — noticeably better final answer.** Concise, no emotional projection, doesn't reach for therapy framing.

---

## New Critical Issue

### NEW-01 — Agent consistently hallucinating that the user is unemployed
**Cases:** st_th_001, st_th_002, st_th_007, st_th_010, st_th_012, st_th_013, st_th_015

This is the most important finding in this run. In 7 out of 16 cases, the draft includes a reference to the user being unemployed when no user in any of these cases mentioned employment at all:

- st_th_001: "You mentioned you're unemployed — that might be a good time to think about how you can gently set limits at work..."
- st_th_002: "You mentioned you're unemployed — and I wonder if that's part of what's making it harder..."
- st_th_007: "You mentioned you're unemployed — that might be part of the weight you're carrying..."
- st_th_015: "You mentioned you're unemployed — that might be part of what's weighing on you..."

The phrase "You mentioned you're unemployed" is fabricated — the user never said this. This is the profile extractor at work: the test user (`test-suite@pfa.internal`) accumulated profile data across all previous test runs. Because `_maybe_extract_profile()` runs after every `respond()` call, earlier cases in the suite extracted and stored profile attributes from the conversation, and later cases then had those attributes injected via `_build_profile_block()`.

This is a dual problem:
1. **Test isolation**: the test user's profile is being polluted across cases within a single run, and across runs. Each case is not starting from a clean state.
2. **Agent behaviour**: even when profile data exists, the agent phrases it as "You mentioned you're unemployed" — as if the user said it in this conversation. That is actively misleading. Profile data should inform tone silently, not be narrated back as a recalled statement.

**Suggested fix (testing):** Reset or create a fresh test user per suite run, or call `user_store.update_extracted_fields` to clear profile fields before each case. Alternatively, run each case with a unique user ID.

**Suggested fix (agent behaviour):** The `_build_profile_block` prompt already says "do not recite these facts back verbatim" — but the agent is paraphrasing them as recalled conversation. Add an explicit instruction: "Do not reference profile information as if the user said it in this conversation. Use it only to adjust your tone."

---

## Remaining Issues from Run 1

### CRT-01 — Critic still misapplies emotion projection to distressed cases
**Cases:** st_th_003, st_th_005, st_th_006, st_th_007, st_th_008, st_th_009

The classification step is working (labels are correct), but the critic is still flagging EMOTION PROJECTION and DISTANCING PHRASES for DISTRESSED messages as rule violations. Examples:

- st_th_008 (explicit technique request — DISTRESSED): critique flags "I'm so glad you're asking for this — it's a really helpful and brave step" as EMOTION PROJECTION. But this message is DISTRESSED and Rule 1 explicitly says [POSITIVE only].
- st_th_005 (student overwhelm — DISTRESSED): critique flags COPING FOR GOOD NEWS even though the message is DISTRESSED. This rule literally cannot apply here.
- st_th_003 (relationship conflict — DISTRESSED): critique flags "I hear how exhausting and frustrating this must feel" as EMOTION PROJECTION — again, DISTRESSED message, rule doesn't apply.

The model classifies correctly, then ignores its own classification when evaluating. The issue is that the rules are described in full even for non-applicable cases, so the model pattern-matches on rule names rather than reading the condition.

**Suggested fix:** Remove the rule text entirely for non-applicable rules rather than just labelling them. For DISTRESSED/AMBIGUOUS messages, don't even show rules 1 and 3 in the prompt — replace them with: "Rules 1 and 3 do not apply to this message. Skip them."

---

### BUG-02 — Partial: same-line double question not caught
**Cases:** st_th_010

The line-based strip catches questions on separate lines but not when two questions appear in the same paragraph connected by "Or maybe":

> "Would you like to try something small today, like sitting quietly for five minutes...? Or maybe you'd prefer to reach out to someone who makes you feel safe?"

Both questions end the same text block. The current `_strip_double_closing_question` only checks the last two non-empty *lines*, not sentence-level question marks.

**Suggested fix:** Add a sentence-level pass after the line-level pass — split the final paragraph by `?` and if there are two or more question sentences, keep only the last one.

---

### REV-01 — Reviser self-check not reliably working
**Cases:** st_th_005, st_th_013, st_th_010

The reviser sometimes makes things worse:

- **st_th_005** (student overwhelm): draft was 4 sentences with violations. Final answer is a fragmented, repetitive block — "That's enough. That's enough." / "You're not alone. I'm here." — well over 5 sentences and still has all the original violations. Critique flagged 9 MUST_FIX items; reviser fixed zero of them substantively.
- **st_th_013** (intrusive thoughts): final answer is longer than the draft, still contains "You mentioned being unemployed" (hallucination), still has "you're not broken" and "you're not alone."
- **st_th_010**: reviser leaked the critique into the final answer again (BUG-01, user deferred).

The self-check instruction ("silently verify each MUST_FIX item is no longer present") isn't being followed. When the critique has many MUST_FIX items, the reviser gets overwhelmed and produces worse output.

**Suggested fix:** Cap MUST_FIX to the 2-3 most critical items in the critique itself, so the reviser has a smaller target. The critique token cap helps with length but not with prioritisation. Add to CRITIC_SYSTEM: "List at most 3 items under MUST_FIX, prioritised by severity."

---

### AGT-01 — Ambiguous/vague cases still mostly skip the follow-up question
**Cases:** st_th_009, st_th_010, st_th_015

The rule change helped with st_th_016 (which now asks "What's been showing up for you lately?" without offering any technique). But the other short/vague cases still jump to suggestions:

- st_th_009 ("A friend suggested I try talking..."): draft goes straight to "write down a few sentences that feel honest, even if they're messy" — no question asked first
- st_th_010 ("Things are fine...feel flat"): jumps straight to grounding exercises
- st_th_015 ("I just feel off"): offers walking and breathing before asking anything

The rule says "two sentences or fewer" — but the model isn't counting sentences precisely. The problem may be that the rule fires on length but not on "I don't know what I'd even say / I don't know how else to put it" cues, which are explicit signals of not knowing where to start.

**Suggested fix:** Add explicit trigger phrases to the rule: "If the user's message contains phrases like 'I don't know what to say', 'I don't know how else to put it', 'I'm not sure where to start', or is two sentences or fewer with no clear topic — ask one question, nothing else."

---

## Case-Level Summary

| Case | Run 1 verdict | Run 2 verdict | Change |
|------|--------------|--------------|--------|
| st_th_001 | NEEDS_REVISION | NEEDS_REVISION | Profile injection added (regression) |
| st_th_002 | APPROVED | NEEDS_REVISION | Profile injection added (regression) |
| st_th_003 | NEEDS_REVISION | NEEDS_REVISION | Similar quality |
| st_th_004 | NEEDS_REVISION | NEEDS_REVISION | Faster (51.9s vs 154.7s) |
| st_th_005 | NEEDS_REVISION | NEEDS_REVISION | Final answer worse |
| st_th_006 | NEEDS_REVISION | NEEDS_REVISION | Similar |
| st_th_007 | NEEDS_REVISION | NEEDS_REVISION | Profile injection added |
| st_th_008 | APPROVED | NEEDS_REVISION | Regression — critic now flags incorrectly |
| st_th_009 | NEEDS_REVISION | NEEDS_REVISION | Similar |
| st_th_010 | NEEDS_REVISION | NEEDS_REVISION | BUG-01 recurs |
| st_th_011 | NEEDS_REVISION | APPROVED | Clear improvement |
| st_th_012 | NEEDS_REVISION | NEEDS_REVISION | Profile injection added |
| st_th_013 | NEEDS_REVISION | NEEDS_REVISION | Faster (62.1s vs 154.3s), but still bad |
| st_th_014 | APPROVED | NEEDS_REVISION | Critic more strict but final answer better |
| st_th_015 | NEEDS_REVISION | NEEDS_REVISION | BUG-01 gone, still jumps to advice |
| st_th_016 | NEEDS_REVISION | NEEDS_REVISION | Asks one question now — improvement |

---

## Recommended Changes (Priority Order)

- [ ] **NEW-01 (testing)**: Create a fresh user per run in the test harness, or clear profile fields before each case — `user_store.update_extracted_fields(user_id, age=None, goals=[], job=None, relationship_status=None)` won't work directly since the method only sets non-None fields. Simplest fix: generate a unique email per run (`test-{run_id}@pfa.internal`).
- [ ] **NEW-01 (agent)**: Add to `_build_profile_block` prompt — "Do not reference these details as if the user mentioned them in this conversation. Never say 'you mentioned X'. Use profile data only to adjust tone."
- [ ] **CRT-01 (remaining)**: For DISTRESSED/AMBIGUOUS messages, suppress rules 1 and 3 entirely in the prompt text rather than just labelling them [POSITIVE only].
- [ ] **REV-01 (remaining)**: Add to CRITIC_SYSTEM — "List at most 3 items under MUST_FIX, in order of severity. Do not list minor or uncertain violations."
- [ ] **BUG-02 (remaining)**: Add sentence-level double-question detection to `_strip_double_closing_question` for same-paragraph cases.
- [ ] **AGT-01 (remaining)**: Add explicit trigger phrases to the vague-message rule in THERAPY_AGENT_SYSTEM.
