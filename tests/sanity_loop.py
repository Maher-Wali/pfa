from agents.therapy_agent import _is_looping_bullet

loop = (
    "- CLINICAL LABELS - the draft does not name any clinical labels. "
    "So this rule is not violated. The draft does not name any clinical labels. "
    "So this rule is not violated. The draft does not name any clinical labels. "
    "So this rule is not violated."
)

clean = (
    "- CLINICAL LABELS - grounding technique violates rule 2, "
    "this is a named programme label and must be replaced with plain language."
)

print("loop detected:", _is_looping_bullet(loop))
print("clean detected as loop:", _is_looping_bullet(clean))
