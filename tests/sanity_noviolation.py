from agents.therapy_agent import _filter_hallucinated_must_fix

draft = (
    'Would you like to try jotting down a few thoughts that pop up at night '
    '-- like "I\'ll never sleep again" or "I have to be perfect" -- '
    'and then gently challenge them with something softer? '
    'Or maybe try a short breathing exercise before bed? '
    'What\'s been sitting with you the most lately?'
)

critique = (
    "VERDICT: NEEDS_REVISION\n"
    "MUST_FIX:\n"
    '- CLINICAL LABELS -- "jotting down a few thoughts" and "gently challenge them" '
    'are not clinical labels, so this is not a violation. So no violation here.\n'
    '- DISTANCING PHRASES -- "You\'re not alone in this" is not a distancing phrase. Not a violation.\n'
    '- TWO-OPTION CLOSING -- The draft contains two questions: '
    '"Would you like to try..." and "What\'s been sitting..." -- violation.\n'
    '- VERBATIM CONTEXT -- No verbatim copying. No violation.\n'
)

result = _filter_hallucinated_must_fix(critique, draft)
print(result)
print("---")
print("surviving bullets:", result.count("\n-"))
