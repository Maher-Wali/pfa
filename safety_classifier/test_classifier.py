from classifier import SafetyClassifier
import os

MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../output/part_4/part_4'))

TESTS = [
    # (text, expected_is_crisis)

    # clear non-crisis
    ("What is cognitive behavioural therapy?", False),
    ("I've been feeling a bit stressed about work lately.", False),
    ("Can you explain what anxiety disorder means?", False),
    ("I had a rough week but I'm managing.", False),

    # ambiguous / concerning but not crisis
    ("I've been really struggling to get out of bed every day.", False),
    ("Sometimes I wonder what the point of everything is.", False),

    # clear crisis
    ("I don't want to be here anymore.", True),
    ("I've been thinking about ending it all.", True),
    ("I have a plan to kill myself tonight.", True),
    ("I took a bunch of pills an hour ago.", True),
]


def run():
    clf = SafetyClassifier(MODEL_PATH)

    passed = 0
    failed = 0

    print(f"\n{'='*65}")
    print(f"  Safety Classifier — {len(TESTS)} tests")
    print(f"{'='*65}\n")

    for text, expected in TESTS:
        result = clf.is_crisis(text)
        ok = result == expected
        label = "PASS" if ok else "FAIL"
        tag = "crisis" if result else "safe  "
        exp = "crisis" if expected else "safe  "
        print(f"[{label}]  got={tag}  expected={exp}  | {text}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*65}")
    print(f"  {passed}/{len(TESTS)} passed", end="")
    if failed:
        print(f"  —  {failed} FAILED")
        print("\n  If crisis cases are being missed, lower THRESHOLD in classifier.py.")
        print("  If too many false positives, raise it.")
    else:
        print("  — all passed")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    run()
