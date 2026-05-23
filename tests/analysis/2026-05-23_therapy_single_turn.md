# Therapy Single-Turn Analysis
**Run:** 2026-05-23_11-08-11
**Cases:** 16 (8 clear struggle, 8 ambiguous)
**Agent:** virtual_therapy

---

## Summary

The pipeline has two critical output bugs (reviser leaking critique text, reviser producing double closing questions) that would be immediately visible to a user. The critique system is over-triggering on distress cases by misapplying rules written for "good news" scenarios. Retrieval has two noticeable mismatches. The ambiguous cases expose a consistent failure: the agent almost never follows its own instruction to ask one question before offering advice when the message is vague.

---

## Critical Bugs

### BUG-01 — Reviser leaks the critique into the final answer
**Cases:** st_th_015

The `final_answer` for st_th_015 ("I just feel off") literally contains the full critique text appended after the response. A user would see something like:

> "Would you like to try something simple...  
> Critique: VERDICT: NEEDS_REVISION  
> MUST_FIX: — EMOTION PROJECTION..."

This is the most severe issue in the run. The reviser received the critique as part of its input and reproduced it verbatim in its output instead of consuming it as instructions.

**Likely cause:** The reviser prompt (`REVISER_SYSTEM`) ends with "Return only the final improved answer — no preamble, no meta-commentary." The model ignored this instruction. Could be a formatting issue in how the critique is passed to the reviser, or the model at temperature 0.35 occasionally failing to follow the output constraint.

**Suggested fix:** Add a hard post-processing strip in `therapy_agent._revise()` — if the output contains `VERDICT:` or `MUST_FIX:`, truncate everything from that point. Also consider adding a stronger instruction in the reviser prompt like "Do not output the critique or any part of it."

---

### BUG-02 — Reviser produces two closing questions after being told to fix that
**Cases:** st_th_016

Critique correctly flags `TWO-OPTION CLOSING`. The reviser's output still ends with:

> "What's one thing you'd like to say, even if it's just a quiet thought?  
> What feels right for you right now?"

Two questions. The exact violation it was told to fix.

**Suggested fix:** Same post-processing approach — detect multiple `?` at end of response and trim to the last one. Also strengthen the reviser system prompt: "If TWO-OPTION CLOSING was flagged, rewrite the closing as a single sentence ending in exactly one question mark."

---

## Reviser Effectiveness

### REV-01 — Reviser often doesn't meaningfully change the draft
**Cases:** st_th_007, st_th_010

In both cases, the critique returns `NEEDS_REVISION` with multiple `MUST_FIX` items, but the final answer is nearly identical to the draft — cosmetic changes only (punctuation, commas removed, line breaks collapsed).

- st_th_007 draft: "I hear how heavy this feels — and that's okay. You're not failing, you're just in a space that's hard to navigate right now..."
- st_th_007 final: "I hear how heavy this feels, and that's okay. You're not failing, you're just in a space that's hard to navigate right now..."

The flagged emotion projection and distancing phrases are still present word for word.

**Suggested fix:** Add a self-check step in the reviser prompt: "Before returning your answer, verify that each item listed under MUST_FIX is no longer present in your revised answer. If any item is still present, fix it now."

---

## Critique Quality

### CRT-01 — Critic misapplies "good news" rules to clear distress cases
**Cases:** st_th_001, st_th_003, st_th_005, st_th_006, st_th_007

Rules 1 (EMOTION PROJECTION) and 3 (COPING FOR GOOD NEWS) are explicitly written for when "the user's message is positive and expresses no struggle." The critic is applying them to cases of clear distress:

- st_th_001: User says "I feel like I'm drowning" — critic flags COPING FOR GOOD NEWS because the draft offered a breathing technique
- st_th_003: User says "I feel like we're stuck in a loop" — critic flags EMOTION PROJECTION
- st_th_007: User describes anhedonia and withdrawal — critic flags EMOTION PROJECTION

In every one of these, the user IS expressing struggle. The draft responses are not violating these rules. The critique is wrong, and the reviser then wastes time "fixing" things that weren't broken.

**Root cause:** The critic system prompt rules are written with "If the user's message is positive" as the condition, but the model is losing track of that condition and applying the rules universally. The rules need clearer separation between the "good news" case and the "distress" case.

**Suggested fix:** Restructure the CRITIC_SYSTEM to make the condition more explicit. Example: add a first step that classifies the user's message as positive/neutral/distressed before evaluating rules, and state clearly which rules only apply to positive messages.

---

### CRT-02 — Critic enters a reasoning loop on some cases
**Cases:** st_th_004, st_th_013

The critique for st_th_013 (intrusive thoughts) is extremely long and repeats "Wait — the draft does not say..." 50+ times. The model got stuck in a self-correction loop. This correlates directly with the worst elapsed times in the run: st_th_004 at 154.7s and st_th_013 at 154.3s, vs 30-60s for most other cases.

**Suggested fix:** Add a `max_tokens` cap to the critique LLM call. The critique only needs to be a few sentences per violation; 200-300 tokens is more than enough. A very long critique is a signal the model is confused, not that it's being thorough.

---

## Retrieval Issues

### RAG-01 — Philosophical question routes to wrong retrieval mode and irrelevant docs
**Cases:** st_th_014

Input: "Do you think it's possible to be genuinely happy without really knowing what you want from life?"

- `retrieval_mode`: `clinical` (routed incorrectly — this is conversational, not clinical)
- Retrieved docs: Bipolar Disorder (Royal College of Psychiatrists), Self-Harm (Mind UK), OCD (Mind UK), BPD (Cleveland Clinic)

All five documents are completely irrelevant. The question contains no clinical keywords, but the routing pushed it to the clinical index anyway. The final answer ignores the docs entirely and responds generically, which is actually fine — but it means the RAG pipeline contributed nothing.

**Suggested fix:** The routing logic in `_route_retrieval_mode` likely needs a "no match / general wellbeing" fallback rather than defaulting to clinical when it doesn't find a therapy match.

---

### RAG-02 — Caretaker fatigue retrieves BPD relationship content
**Cases:** st_th_011

Input: "My partner has been going through a hard time and I've been trying to support them. I think it's affecting me more than I expected."

All 5 retrieved docs are "How to Have Healthy Relationships with BPD." The word "partner" pulled the retriever toward relationship/BPD content. The actual need is compassion fatigue / supporting a struggling loved one — none of the retrieved docs cover that.

The draft ignores the docs entirely and gives a generic response, which is the right instinct but means retrieval is doing no useful work here.

**Suggested fix:** This is a harder problem — the query needs to be understood at the level of "the user is the caregiver, not the person with BPD." One option is to add a query rewriting step for caretaker-framing messages before passing to the retriever.

---

## Agent Behaviour

### AGT-01 — Ambiguous/vague messages should trigger a follow-up question, not advice
**Cases:** st_th_009, st_th_010, st_th_011, st_th_012, st_th_015, st_th_016

The `THERAPY_AGENT_SYSTEM` explicitly says:
> "When the user's opening message is short or vague, prioritize understanding their situation before offering techniques or exercises. Ask one question to learn more rather than suggesting something you have no context for yet."

This rule is being ignored in every ambiguous case. Examples:

- st_th_009 ("A friend suggested I try talking to someone. I don't really know what I'd even say.") → agent immediately suggests writing a sentence down, no question asked
- st_th_010 ("Things are fine...I just feel a bit flat") → agent immediately goes into grounding exercises
- st_th_015 ("I just feel off. I don't know how else to put it.") → agent offers breathing and walking before understanding anything

The correct response to st_th_015 would be something like: "That's okay — sometimes it's hard to name. Can you tell me a little more about when it started, or what 'off' feels like for you?" Instead the agent assumes distress and offers techniques.

**Suggested fix:** The system prompt guideline isn't strong enough — it says "prioritize" but doesn't prohibit offering techniques. Consider making it a hard rule: "If the user's first message is under 2 sentences or explicitly says they don't know what to say/feel, do not offer any technique or suggestion. Ask exactly one question."

---

### AGT-02 — Closing question is always the same phrase
**Cases:** st_th_001, st_th_002, st_th_003, st_th_004, st_th_005, st_th_006, st_th_007, st_th_009, st_th_010, st_th_011, st_th_014, st_th_015, st_th_016

"What feels right for you right now?" appears as the closing question in 13 out of 16 cases. The system prompt says to end with "one open question" but the model has latched onto this single phrase as a template.

This makes the agent feel formulaic. A user who chats more than once will notice the pattern immediately.

**Suggested fix:** Add to the system prompt: "Vary your closing question. The question should be specific to what the person has just shared, not a generic filler phrase."

---

## Positive Observations

- **st_th_002** (grief): APPROVED on first draft. Strong response — emotionally grounded, doesn't rush to advice, appropriate RAG retrieval (grief therapy docs).
- **st_th_008** (breathing technique request): APPROVED. Clean, direct, follows the explicit request without over-qualifying.
- **st_th_014** (philosophical question): Despite bad retrieval, the final answer is calm and thoughtful. The reviser and draft both handled the philosophical framing well without projecting distress.
- Retrieval mode routing works correctly for most distress cases — therapy mode is consistently selected when appropriate.

---

## Recommended Changes

- [ ] **BUG-01**: Add post-processing strip in `therapy_agent._revise()` to remove any content after `VERDICT:` in the output
- [ ] **BUG-02**: Add post-processing to detect and remove duplicate closing questions (count `?` occurrences at end of response)
- [ ] **REV-01**: Add self-check instruction to `REVISER_SYSTEM`: verify each MUST_FIX item is resolved before returning
- [ ] **CRT-01**: Restructure `CRITIC_SYSTEM` — add a classification step at the top (positive/distressed) so rules 1 and 3 are only evaluated when message is positive
- [ ] **CRT-02**: Cap critique output tokens (200-300 max) to prevent reasoning loops
- [ ] **RAG-01**: Review `_route_retrieval_mode` to add a general wellbeing / no-match fallback instead of defaulting to clinical
- [ ] **RAG-02**: Investigate adding a query rewriting step for caretaker-framing messages
- [ ] **AGT-01**: Strengthen the vague-message rule in `THERAPY_AGENT_SYSTEM` — make it a hard prohibition, not a priority
- [ ] **AGT-02**: Add instruction to vary the closing question and make it specific to what was shared
