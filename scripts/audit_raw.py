"""
Quick quality audit of raw scraped JSON files.
Usage: python scripts/audit_raw.py
"""
import json
from pathlib import Path

FILES = {
    # DB1
    "mental_health_foundation": "data/raw/db1_clinical/mental_health_foundation/mental_health_foundation_clinical.json",
    "medlineplus":              "data/raw/db1_clinical/medlineplus/medlineplus_clinical.json",
    "better_health":            "data/raw/db1_clinical/better_health/better_health_clinical.json",
    "rcpsych":                  "data/raw/db1_clinical/rcpsych/rcpsych_clinical.json",
    "camh":                     "data/raw/db1_clinical/camh/camh_clinical.json",
    # DB2
    "getselfhelp":              "data/raw/db2_therapy/getselfhelp/getselfhelp_therapy.json",
}

ROOT = Path(__file__).resolve().parents[1]

SEP = "-" * 70


def is_garbage(text: str) -> bool:
    if not text or len(text) < 30:
        return True
    lr = sum(c.isalpha() for c in text) / len(text)
    words = text.split()
    awl = sum(len(w) for w in words) / max(len(words), 1)
    return lr < 0.50 or awl < 2.5


def audit(name: str, path: Path):
    if not path.exists():
        print(f"{name}: FILE NOT FOUND — {path}")
        return

    records = json.loads(path.read_text(encoding="utf-8"))
    if not records:
        print(f"{name}: EMPTY FILE")
        return

    content_key = "content" if "content" in records[0] else "raw_content"
    texts = [r.get(content_key, "") for r in records]

    wcs = [len(t.split()) for t in texts if t]
    garbage_count = sum(1 for t in texts if is_garbage(t))
    empty_count = sum(1 for t in texts if not t)

    letter_ratios = []
    avg_wls = []
    for t in texts:
        if not t:
            continue
        letter_ratios.append(sum(c.isalpha() for c in t) / len(t))
        words = t.split()
        avg_wls.append(sum(len(w) for w in words) / max(len(words), 1))

    avg_lr = sum(letter_ratios) / max(len(letter_ratios), 1)
    avg_awl = sum(avg_wls) / max(len(avg_wls), 1)

    pct_garbage = 100 * garbage_count // max(len(records), 1)
    pct_good = 100 - pct_garbage

    print(SEP)
    print(f"SOURCE : {name}")
    print(f"FILE   : {path.name}")
    print(f"RECORDS: {len(records)}  |  empty={empty_count}  |  garbage={garbage_count} ({pct_garbage}%)  |  good={len(records)-garbage_count} ({pct_good}%)")
    if wcs:
        wcs_s = sorted(wcs)
        print(f"WORDS  : min={min(wcs)}  median={wcs_s[len(wcs_s)//2]}  max={max(wcs)}")
    print(f"QUALITY: avg_letter_ratio={avg_lr:.3f}  avg_word_len={avg_awl:.2f}")

    # show 2 sample previews
    good_samples = [t for t in texts if not is_garbage(t)]
    for i, t in enumerate(good_samples[:2]):
        preview = t[:250].replace("\n", " ")
        preview = preview.encode("ascii", errors="replace").decode("ascii")
        print(f"SAMPLE {i+1}: {preview}")

    # show any garbage samples
    bad_samples = [t for t in texts if is_garbage(t) and t]
    if bad_samples:
        gs = bad_samples[0][:200].replace("\n", " ").encode("ascii", errors="replace").decode("ascii")
        print(f"GARBAGE SAMPLE: {gs}")


def main():
    print("Raw data quality audit\n")
    for name, rel_path in FILES.items():
        audit(name, ROOT / rel_path)
    print(SEP)


if __name__ == "__main__":
    main()
