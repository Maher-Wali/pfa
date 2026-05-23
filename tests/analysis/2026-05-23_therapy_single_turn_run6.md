# Therapy Single-Turn Analysis — Run 6
**Run:** 2026-05-23_14-26-32
**Previous run:** 2026-05-23_14-09-20
**Fixes applied before this run:** CRITIC-HALLUC scope instruction (evaluate DRAFT ANSWER only)

---

## What Improved

- **CRITIC-HALLUC mostly resolved.** The fabricated DBT/CBT clinical labels in st_th_010 and st_th_011 are gone. The scope instruction worked for the majority of cases.
- **REV-LOOP-2 resolved.** st_th_004 is clean at 35.7s — no garbage output, no self-arguing text. The critic correctly approved it and the reviser was not needed.
- **BUG-01 (meta-notes) gone.** No `*Note:` suffixes in any final answer.
- **New approvals:** st_th_001, st_th_004, st_th_007, st_th_011 — all recovered from run 5 regressions.
- **Approved this run: 8/16** (st_th_001, st_th_003, st_th_004, st_th_005, st_th_007, st_th_008, st_th_011, st_th_015). Up from 5/16 in run 5.

---

## Remaining Critical Issues

### CRITIC-HALLUC residual — st_th_006 still inventing terms
**Case:** st_th_006

The scope instruction eliminated most hallucinations but st_th_006's critique still invented terms not present in the draft: "anxiety ladder", "STOPP skill", and claims the draft uses "social anxiety disorder" and "STOPP" — none of which appear in the draft text. The critique also misquotes the draft: it attributes "what if we tried something small…" as a distancing phrase, but the draft says "Would you like to try one small thing together."

The scope instruction is not preventing the critic from fabricating quoted excerpts. A stronger gate is needed: the critic should be required to quote exact text before flagging.

**Suggested fix:** Add to the scope instruction: "Before flagging any violation, quote the exact phrase from the DRAFT ANSWER. If you cannot find the exact phrase in the draft, do not flag it."

---

### CRITIC-SELF-CORRECT still occurring — st_th_002 critique cut off mid-correction
**Case:** st_th_002

The critique for st_th_002 is visibly self-correcting mid-response (discusses VERBATIM CONTEXT, then backs off, ends the response cut off mid-sentence). It hit the 400-token cap while revising its own reasoning. The self-correction fix was recommended in run 5 but not yet applied.

As a result: the reviser received a truncated critique and produced a final answer that still has a three-option closing — "Would you like to try something gentle, like writing a letter, making a memory box, or simply sitting with the sadness?" — which is three suggestions, not a single open question.

**Suggested fix (not yet applied):** Add to CRITIC_SYSTEM: "Do not write 'Wait', 'Correction', 'Let me recheck', or revise your findings mid-response. State each finding once and finalize it."

---

### CRITIC false positive — "breathing exercise" flagged as clinical label
**Case:** st_th_001

The critic flagged "breathing exercise" as a CLINICAL LABELS violation. "Breathing exercise" is plain everyday language — the clinical labels rule targets specific named techniques like "grounding technique", "cognitive restructuring", "EMDR", or "mindfulness meditation", not generic descriptions of an activity.

The reviser handled this by removing the mention entirely and producing a good final answer, so the user-facing quality was acceptable. But the false positive risks degrading good drafts in future cases.

**Suggested fix:** Add plain language carve-outs to rule 2 in CRITIC_SYSTEM: "Plain language descriptions like 'breathing exercise', 'deep breaths', 'a short walk' are NOT clinical labels. Only flag specific named techniques (e.g. 'grounding technique', 'cognitive restructuring', 'EMDR', 'mindfulness meditation', 'DBT skill')."

---

### TWO-OPTION CLOSING detection inconsistent — critic misses body questions and "or" patterns
**Cases:** st_th_010, st_th_013, st_th_014, st_th_016

The critic reliably catches explicit "or maybe" patterns at the closing line but misses:

- **st_th_010** body: "Would you like to try something small, like walking for five minutes? Or maybe you could sit with a cup of tea…" — two options mid-response, followed by a separate closing question. Two questions total.
- **st_th_013** closing: "What's one small thing you'd like to try with those thoughts, or what's one thing that feels most important to you right now?" — "or what's one thing" is a second question.
- **st_th_014** closing: "Would you like to try something simple today, like walking for 10 minutes, or just sitting with a cup of tea…" — two options.
- **st_th_016** closing: "What's the first thing that comes to mind…?" in the body + "what's the one thing you'd like to say, even if it's just a whisper?" at the close — two questions.

The rule catches "or maybe" reliably but misses plain "or" in embedded options and misses two questions spread across body and closing.

**Suggested fix:** Extend rule 6 in CRITIC_SYSTEM: "Also flag if the response contains more than one question anywhere in the full response — a question in the body followed by a closing question is a violation. Check the entire response, not only the last line."

---

### CLINICAL LABEL missed — "Distract with ACCEPTS"
**Case:** st_th_012

The draft says: "like using one of the 'Distract with ACCEPTS' options" — this is a named DBT technique and a clear CLINICAL LABELS violation. The critic approved it. The scope instruction may have made the critic hesitant to flag terms that look like they could be from the context, even when they genuinely appear in the draft.

**Suggested fix:** Add "named DBT or ACT skill names (e.g. 'Distract with ACCEPTS', 'PLEASE skill', 'TIPP skill', 'STOP skill')" to the examples in rule 2.

---

### AGT-01 — Still not working for st_th_009, st_th_013
**Cases:** st_th_009, st_th_013

Both messages contain explicit trigger phrases ("I don't really know what I'd even say", "I don't know if that's normal"). Both drafts still offer specific scripts or techniques instead of asking one question. This has not changed across runs 4–6.

---

## Case-Level Summary

| Case | Run 4 | Run 5 | Run 6 | Trend |
|------|-------|-------|-------|-------|
| st_th_001 | NR | NR | **APPR** | Improved — false clinical label flag, but reviser fixed real violation |
| st_th_002 | NR | NR | NR | Critique self-corrects, hits token cap; 3-option closing not fixed |
| st_th_003 | APPR | APPR | **APPR** | Stable |
| st_th_004 | NR | NR | **APPR** | REV-LOOP-2 gone; clean |
| st_th_005 | APPR | APPR | **APPR** | Stable |
| st_th_006 | APPR | NR | NR | Critic still hallucinating invented terms |
| st_th_007 | APPR | NR | **APPR** | Recovered |
| st_th_008 | APPR | APPR | **APPR** | Stable |
| st_th_009 | NR | NR | NR | AGT-01 still failing |
| st_th_010 | APPR | NR | NR | Body two-option + double question, critic missed |
| st_th_011 | APPR | NR | **APPR** | Recovered |
| st_th_012 | APPR | NR | NR | "Distract with ACCEPTS" not caught |
| st_th_013 | NR | NR | NR | AGT-01 + double closing question not caught |
| st_th_014 | APPR | APPR | NR | Regressed — TWO-OPTION closing missed |
| st_th_015 | APPR | APPR | **APPR** | Stable |
| st_th_016 | APPR | APPR | NR | Double closing question not caught |

---

## Recommended Changes (Priority Order)

- [ ] **CRITIC-HALLUC residual**: Add to scope instruction in CRITIC_SYSTEM: *"Before flagging any violation, quote the exact phrase from the DRAFT ANSWER. If you cannot find the exact phrase in the draft, do not flag it."*
- [ ] **CRITIC-SELF-CORRECT**: Add to CRITIC_SYSTEM: *"Do not write 'Wait', 'Correction', 'Let me recheck', or revise your findings mid-response. State each finding once and finalize it."*
- [ ] **CLINICAL LABELS false positive**: Add plain language carve-outs to rule 2: *"Plain language descriptions like 'breathing exercise', 'deep breaths', 'a short walk' are NOT violations. Only flag specific named techniques (e.g. 'grounding technique', 'cognitive restructuring', 'EMDR') or named skill sets (e.g. 'Distract with ACCEPTS', 'PLEASE skill', 'TIPP skill')."*
- [ ] **TWO-OPTION CLOSING — full response check**: Add to rule 6: *"Also flag if the response contains more than one question anywhere — a question in the body followed by a closing question is a violation. Check the entire response, not only the last line."*
- [ ] **AGT-01**: Move vague-message rule to top of THERAPY_AGENT_SYSTEM guidelines and add a bad/good example.
