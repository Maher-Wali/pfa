import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MAX_LENGTH = 512
# Threshold on P(crisis) — lower = more sensitive, higher = fewer false positives.
THRESHOLD = 0.6


class SafetyClassifier:
    def __init__(self, model_path: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def is_crisis(self, text: str) -> bool:
        try:
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=MAX_LENGTH,
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                logits = self.model(**inputs).logits

            p_crisis = torch.softmax(logits, dim=-1)[0][1].item()
            return p_crisis >= THRESHOLD

        except Exception:
            # Fail safe — never fail open
            return True
