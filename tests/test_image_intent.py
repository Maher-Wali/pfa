from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.image_generation import is_image_request

# (prompt, expected)
FIXTURES: list[tuple[str, bool]] = [
    # --- should trigger ---
    ("generate an image for this post", True),
    ("create a visual for the Facebook post we just wrote", True),
    ("make a photo to go with this article", True),
    ("draw an illustration of a person meditating", True),
    ("produce a graphic for our anxiety awareness campaign", True),
    ("design a banner for the mental health week event", True),
    ("render a poster for this therapy service", True),
    ("can you create an image of a calm sunrise?", True),
    ("generate a thumbnail for the blog", True),
    ("I want a picture to go with this caption", False),  # "want" too ambiguous — known limitation
    ("make me a visual for this Instagram post", True),
    ("create pictures that match this content", True),
    # noun-first / no explicit verb
    ("an image where a person is sitting calmly by a window", True),
    ("a photo where the colors are soft and warm", True),
    ("a visual where people look happy and connected", True),
    ("an illustration where a therapist is listening attentively", True),
    ("a poster where the background is a calm blue gradient", True),
    # --- should NOT trigger ---
    ("write a Facebook post about anxiety", False),
    ("what are the symptoms of depression?", False),
    ("help me improve this caption", False),
    ("I feel overwhelmed lately", False),
    ("can you summarize this article?", False),
    ("give me tips for better sleep", False),
    ("what is CBT?", False),
    ("rewrite this post in a warmer tone", False),
    ("I have a vivid image in my mind of what I want to say", False),
    ("picture this: a calm morning routine", False),
]


def run() -> None:
    passed = 0
    failed = 0

    for prompt, expected in FIXTURES:
        result = is_image_request(prompt)
        status = "PASS" if result == expected else "FAIL"
        if result != expected:
            failed += 1
            print(f"{status}  expected={expected}  got={result}  | {prompt!r}")
        else:
            passed += 1

    total = passed + failed
    print(f"\n{passed}/{total} passed", "OK" if failed == 0 else f"-- {failed} failed")


if __name__ == "__main__":
    run()
