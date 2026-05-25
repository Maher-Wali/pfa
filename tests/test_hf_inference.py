"""Quick standalone test for HF image generation — run directly with python."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

MODEL = "black-forest-labs/FLUX.1-dev"
PROMPT = "a calm sunrise over a mountain, soft warm colors, minimalist"

api_key = os.getenv("IMAGE_GENERATION_KEY")
print(f"Key loaded: {bool(api_key)}")
print(f"Key prefix: {api_key[:8] if api_key else 'None'}")

if not api_key:
    print("ERROR: IMAGE_GENERATION_KEY not set in .env")
    sys.exit(1)

try:
    from huggingface_hub import InferenceClient
    from huggingface_hub.errors import HfHubHTTPError
except ImportError:
    print("ERROR: huggingface_hub not installed")
    sys.exit(1)

print(f"\nCalling {MODEL}...")
client = InferenceClient(api_key=api_key)

try:
    image = client.text_to_image(prompt=PROMPT, model=MODEL)
    print("SUCCESS: image generated")
    out = Path("tests/test_output.png")
    image.save(out)
    print(f"Saved to {out}")
except HfHubHTTPError as exc:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    body = getattr(exc, "response", None) and exc.response.text
    print(f"HfHubHTTPError {status}: {body}")
except Exception as exc:
    print(f"{type(exc).__name__}: {exc}")
