# Therapy Single-Turn Analysis — Run 3
**Run:** 2026-05-23_13-17-36
**Previous run:** 2026-05-23_12-51-47
**Fixes applied before this run:** Fresh user per run (NEW-01)

---

## What Improved

- **Profile contamination fully eliminated.** Zero "unemployed" hallucinations across all 16 cases. Clean baseline.
- **st_th_015 APPROVED** ("I just feel off") — first time this case passes. The agent asks "what's been happening lately that's made this feeling feel different?" instead of jumping to advice. AGT-01 is working for this specific case.
- **st_th_008** (breathing technique request) — clean, direct, step-by-step. Good quality.
- **st_th_012** draft — the draft itself is concise and asks an open question ("What's helping you carry it, or what's making it harder, right now?"). Good drafting instinct.
- **st_th_013** final answer — calm, non-clinical, ends with a relevant single question about intrusive thoughts.
- Critique response times are broadly stable (26s–68s), no multi-minute loops except st_th_016.

---

## Critical New Issue

### CRIT-01 — Reviser entered an infinite loop on st_th_016
**Case:** st_th_016 — elapsed: 165.0s

The final answer for st_th_016 is the draft repeated verbatim approximately 30 times back to back. The reviser had no token cap, hit the model's maximum output window, and filled it with repetitions of the same paragraph. This is BUG-01's cousin — instead of leaking the critique, the reviser looped on its own output.

The critique for st_th_016 is also long and partially self-contradictory (it flags the same items multiple times in sequence), which likely confused the reviser into a generation loop.

**Suggested fix:** Apply the same `max_tokens` cap to the reviser call (`_revise()`) as was applied to the critique. 500-600 tokens is enough for a 3-5 sentence final answer.

---

## Persistent Issues

### CRT-01 — Critic still applies emotion projection rules to DISTRESSED messages
**Cases:** st_th_001, st_th_002, st_th_003, st_th_005, st_th_006, st_th_007, st_th_008, st_th_009, st_th_011, st_th_013, st_th_016

The [POSITIVE only] annotation is not working. The model classifies the message correctly — every case now shows "User message: DISTRESSED" — but then ignores that classification and applies rules 1 and 3 anyway. In st_th_001 the critic even writes:

> "which project emotional validation and imply the user is struggling — **this is appropriate for DISTRESSED messages**"

...then flags it as a violation anyway. The rule label is visible in the output but the model overrides it.

This is a prompt architecture problem. Adding a label to a rule that the model should skip is not enough — the model pattern-matches on the rule name and flags it regardless. The label needs to be a gate, not a note.

**Suggested fix:** For DISTRESSED and AMBIGUOUS messages, physically remove rules 1 and 3 from the prompt. Replace them at runtime with a placeholder: "Rules 1 and 3 are not applicable to this message type. Do not evaluate them." This requires building the critic prompt dynamically based on message classification — either pre-classify in the agent before calling the critic, or split into two critic prompts (one for positive, one for distressed/ambiguous).

---

### REV-01 — Reviser over-corrects when MUST_FIX list is long
**Cases:** st_th_009, st_th_012

When the critique returns many MUST_FIX items, the reviser now tends to strip the response down to almost nothing rather than fix individual items:

- **st_th_009** ("A friend suggested I try talking to someone"): final answer is four short sentences ending in "That's enough." — no acknowledgment of why the user is there, no question asked, no warmth. A user receiving this would feel dismissed.
- **st_th_012** (minimising, compares to others): final answer is a single question: "What's one thing you're holding onto right now that's making it hard to breathe, or that's just too heavy to let go of?" The draft was actually decent — the reviser threw it all away.

Over-stripping is a direct consequence of a long MUST_FIX list with no priority — the reviser deletes everything flagged, which is often most of the content.

**Suggested fix (already noted in run 2):** Cap MUST_FIX to 2-3 items in the critique itself. When the reviser has a short, prioritised list it fixes surgically rather than discarding everything.

---

### BUG-02 — Same-line double question still not caught
**Cases:** st_th_004

Final answer: "Do you want to try that breath pause tonight, or maybe we can talk about what's making your mind feel restless, even if it's just a few minutes?" — two options in one line, `_strip_double_closing_question` only checks line boundaries so this isn't caught.

Also st_th_002: "What's one small thing you could do today, even if it's just a little, that feels safe, even if it's just a little?" — "even if it's just a little" appears twice in the same sentence, making the question read awkwardly (not a double question but a reviser carelessness issue).

---

### CRT-01 — Misclassification: st_th_010 labelled DISTRESSED, should be AMBIGUOUS
**Case:** st_th_010

Input: "Things are fine, honestly. I just feel a bit flat lately. Like everything's fine on paper but I don't feel much."

The user opens with "Things are fine, honestly" — this is the definition of AMBIGUOUS (not positive, not distressed). The critic classifies it DISTRESSED and then applies distress-level scrutiny to a response that should be gentle and exploratory. The final answer ends up offering suggestions ("a short walk, a cup of tea") when the correct response for this case is a single question to understand more.

---

### AGT-01 — Still not triggering for most ambiguous cases
**Cases:** st_th_009, st_th_010, st_th_013, st_th_014

The rule is working for st_th_015 ("I just feel off") but not for the others. The cases where it's still failing all have messages that are slightly longer than two sentences, so the length trigger doesn't fire. The real signal — "I don't know what I'd even say", "I don't really know what to say", "I don't know if that's normal" — isn't being caught as a vague-message cue.

---

## Case-Level Summary

| Case | Run 1 | Run 2 | Run 3 | Trend |
|------|-------|-------|-------|-------|
| st_th_001 | NR | NR | NR | Stable (draft good, critic wrong) |
| st_th_002 | APPR | NR | NR | Regressed |
| st_th_003 | NR | NR | NR | Stable |
| st_th_004 | NR | NR | NR | Stable, BUG-02 persists |
| st_th_005 | NR | NR | NR | Stable but final answer over-stripped |
| st_th_006 | NR | NR | NR | Stable |
| st_th_007 | NR | NR | NR | Stable |
| st_th_008 | APPR | NR | NR | Regressed (critic over-flags) |
| st_th_009 | NR | NR | NR | Final answer too bare |
| st_th_010 | NR | NR | NR | Misclassified as DISTRESSED |
| st_th_011 | NR | APPR | NR | Regressed (critic loop hit token cap) |
| st_th_012 | NR | NR | NR | Final answer too stripped |
| st_th_013 | NR | NR | NR | Improved quality |
| st_th_014 | APPR | NR | NR | Final answer decent |
| st_th_015 | NR | NR | **APPR** | Improved — AGT-01 working here |
| st_th_016 | NR | NR | NR | Catastrophic loop (165s) |

---

## Recommended Changes (Priority Order)

- [ ] **CRIT-01**: Add `max_tokens` cap to `_revise()` call (500-600 tokens). Same fix as critique token cap.
- [ ] **CRT-01 (root fix)**: Move message classification out of the critic and into the agent. Pre-classify the message in `respond()` before calling `_critique()`, then build the critic prompt dynamically — omit rules 1 and 3 entirely for DISTRESSED/AMBIGUOUS messages.
- [ ] **REV-01**: Add to CRITIC_SYSTEM — "List at most 2 items under MUST_FIX, the two most severe only. Do not list uncertain or borderline violations."
- [ ] **AGT-01**: Extend trigger phrases in THERAPY_AGENT_SYSTEM: add "I don't know what I'd even say", "I don't know if that's normal", "I don't really know" as explicit vague-message cues.
- [ ] **BUG-02**: Extend `_strip_double_closing_question` to detect same-line double questions by scanning for two `?` within the last paragraph.
