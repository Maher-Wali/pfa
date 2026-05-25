# Therapy Agent — Multi-Turn Suite Analysis
**Run:** `2026-05-23_19-21-24`  
**Suite:** `therapy_multi_turn`  
**Conversations:** 3 | **Total turns:** 12  
**All safe_mode:** false | **All retrieval_mode:** therapy

---

## Summary

All 12 turns completed without errors and all critiques were ultimately approved. Two turns required revision before approval (mt_th_003 turns 2 and 3), which correlated with the two longest response times in the run. The agent demonstrated consistent empathy and topical coherence across conversations, but a recurring formulaic closing question and some cross-turn repetition are the main quality concerns.

---

## Per-Conversation Breakdown

### mt_th_001 — Work Stress → Coping → Follow-Through

| Turn | Input summary | Critique | Elapsed |
|------|--------------|----------|---------|
| 1 | Stressed at work, deadlines moving | APPROVED | 45.5s |
| 2 | "Say yes to everything" problem | APPROVED | 38.9s |
| 3 | How to say no without guilt | APPROVED | 48.3s |
| 4 | What if manager pushes back | APPROVED | 60.5s |

**What worked:**
- Turn 1 opens with validation of uncertainty (not just workload), which is more therapeutically targeted than a generic stress acknowledgement.
- Turn 2 correctly identifies the boundary-setting angle and retrieves DBT boundary-setting docs, an appropriate modality shift.
- Turn 4 provides a concrete script the user can say aloud, which is actionable without being prescriptive.

**Issues:**
- Turn 2 references "the to-do list thing" in the retrieved draft phrasing but no to-do list was mentioned in turn 1. This is a continuity artifact — the user's turn 2 input itself says "the to-do list thing sounds useful," implying the agent suggested it in an earlier exchange not captured here, OR the user is responding to something the RAG context implied. Either way the agent's turn 2 response doesn't address this reference at all, missing a continuity opportunity.
- Turns 3 and 4 share an almost identical closing paragraph: *"What if we tried one small thing, say 'no' to something that feels 'not urgent'..."* — verbatim repetition across consecutive turns signals a formulaic pattern rather than genuine turn-by-turn adaptation.
- Turn 4 elapsed 60.5s — the longest in this conversation — without a meaningfully longer or more complex response than turn 3 (48.3s).

---

### mt_th_002 — Grief — Opening Up Gradually

| Turn | Input summary | Critique | Elapsed |
|------|--------------|----------|---------|
| 1 | Lost someone, unsure if ready to talk | APPROVED | 28.8s |
| 2 | Best friend, car accident, survivor guilt | APPROVED | 33.2s |
| 3 | Logical vs. felt guilt | APPROVED | 33.6s |
| 4 | Daily habit reminder now painful | APPROVED | 40.7s |

**What worked:**
- Turn 1 correctly holds space without pushing — no techniques, no directive — appropriate for stated ambivalence about talking. The pacing is the best across the whole suite.
- Turn 2 validates the survivor guilt reflex without pathologizing it, which aligns with grief therapy best practices.
- Turn 3 addresses the logical/felt split directly: distinguishes knowing from feeling, avoids trying to resolve the guilt cognitively.
- Retrieval was consistently relevant (grief therapy modality throughout).

**Issues:**
- Turn 2 retrieval included "Intrusive Thoughts" (CBT) docs alongside grief therapy docs. While technically relevant (intrusive thoughts about the accident), the agent did not draw on them in the response, making them noise in the retrieved set.
- The phrase *"what it's asking for from you"* appears as the closing question in turns 2, 3, and 4. By turn 4 it has become a verbal tic rather than a genuine exploratory question, which can feel hollow in grief conversations where the user is looking for concrete ways people survive loss (their explicit question in turn 4: *"How do people get through this?"*).
- Turn 4 doesn't actually answer the user's question. They asked *how do people get through this* — a direct request for normalizing information. The response pivots back to an introspective exercise instead of first answering the question and then grounding.

---

### mt_th_003 — Anxiety Technique → Feedback Loop

| Turn | Input summary | Critique | Elapsed |
|------|--------------|----------|---------|
| 1 | Everything overwhelming, where to start | APPROVED | 29.2s |
| 2 | Give me one concrete thing to try | NEEDS_REVISION → APPROVED | 59.7s |
| 3 | Tried 4-7-8 breathing, mind wandered — normal? | NEEDS_REVISION → APPROVED | 61.7s |
| 4 | Anxiety at work, can't do breathing in public | APPROVED | 43.5s |

**What worked:**
- Turn 1 correctly avoids overwhelming the user with options and anchors to a single small action.
- Turn 3 directly validates that mind-wandering during mindfulness is normal and expected — accurate, reassuring, and grounded in the retrieved MBSR material.
- The conversation arc (technique offered → user tries it → reports back → requests adaptation) is well-handled structurally: the agent tracks the user's stated experience and adapts rather than ignoring it.

**Issues:**
- Turns 2 and 3 both required revision (the only two in the full suite). Both are also the two slowest turns overall (59.7s, 61.7s). The critique field shows `VERDICT: NEEDS_REVISION\nVERDICT: APPROVED`, indicating a second critique pass was needed, which explains the extra latency.
- Turn 4 is the weakest response in the suite. The user explicitly asked for a **discreet** in-the-moment strategy at their desk, but the final answer suggests noticing breath and posture — which is essentially the same breathing-based approach the user just flagged as socially impractical. A better response would have pivoted to a grounding technique (e.g., 5-4-3-2-1 sensory, feet-on-floor, cold water) that requires no visible behavior. The retrieved docs (social anxiety CBT) contained relevant content that was not surfaced.
- Turn 3's draft contains the preamble *"It's completely normal..."* — this is therapeutically sound, but the revision note suggests the original draft had quality issues the critique caught, yet the approved final answer is nearly identical to the draft, which is unusual. The revision may have been cosmetic (punctuation/tone) rather than substantive.

---

## Cross-Conversation Patterns

### Critique pipeline
- 10/12 turns: single-pass approval
- 2/12 turns: NEEDS_REVISION → APPROVED (both in mt_th_003)
- No turn failed final approval
- The NEEDS_REVISION cases added ~20-25s each, consistent with a second LLM call for re-critique

### Draft → Final transformation
The draft-to-final edit is consistently the same mechanical transformation: em-dashes (`—`) replaced with commas, curly quotes (`"..."`) removed or straightened, run-on filler phrases trimmed. This is punctuation normalization, not substantive revision. Confirms the critique is focused on tone/safety rather than content depth.

### Retrieval quality
| Conversation | Modality match | Noise docs |
|---|---|---|
| mt_th_001 | CBT stress → DBT boundaries (appropriate shift) | None |
| mt_th_002 | Grief therapy throughout | 1 (Intrusive Thoughts, turn 2) |
| mt_th_003 | CBT/relaxation throughout | Social anxiety docs in turn 4 were relevant but unused |

### Latency
```
Min:    28.8s  (mt_th_002 turn 1)
Max:    61.7s  (mt_th_003 turn 3, post-revision)
Median: ~41s
```
Turns requiring revision roughly double in elapsed time. All turns are slow by chatbot standards; the pipeline involves at least draft generation + critique + optional revision, which compounds latency.

### Formulaic closing question
The closing question *"What's one small/tiny thing you could do right now..."* appears in **8 of 12 turns**. This template closes even turns where the user asked a direct, answerable question (mt_th_002 turn 4, mt_th_003 turn 4). Over a multi-turn conversation this pattern becomes predictable and undermines authenticity — users who notice it may disengage.

---

## Recommendations

| Priority | Issue | Suggested fix |
|---|---|---|
| High | Turn 4 of mt_th_003 doesn't answer the question asked | Critique prompt should flag when a user asks a direct question and the draft ignores it |
| High | Formulaic closing question | Add a critique check that penalizes consecutive use of the same closing template |
| Medium | mt_th_002 turn 4 sidesteps a direct "how do people cope" question | Add a rule: answer the stated question first, ground second |
| Medium | Turns 2-3 of mt_th_003 both required revision | Investigate what the NEEDS_REVISION critiques flagged — if it's the same issue twice, a draft prompt adjustment would prevent both |
| Low | Intrusive Thoughts doc retrieved in grief conversation | Acceptable noise, but a re-ranking step that boosts modality-matched docs could reduce it |
| Low | Latency (28-62s range) | Parallelizing draft generation and RAG retrieval, if not already done, is the highest-yield optimization |
