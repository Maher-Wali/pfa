from __future__ import annotations

from typing import Literal

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline


SafetyLabel = Literal["NOT_CRITICAL", "CONCERNING", "CRITICAL"]


class MentalSafetyClassifier:
    def __init__(self, model_name: str):
        self.model_name = model_name

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)

        device = 0 if torch.cuda.is_available() else -1

        self.pipe = pipeline(
            task="text-classification",
            model=self.model,
            tokenizer=self.tokenizer,
            device=device,
            truncation=True,
            max_length=512,
        )

    def classify(self, conversation_text: str) -> SafetyLabel:
        result = self.pipe(conversation_text)[0]
        raw_label = str(result["label"]).upper()

        return self._normalize_label(raw_label)

    def _normalize_label(self, label: str) -> SafetyLabel:
        if "CRITICAL" in label and "NOT" not in label:
            return "CRITICAL"

        if "CONCERNING" in label:
            return "CONCERNING"

        if "NOT" in label or "SAFE" in label or "NORMAL" in label:
            return "NOT_CRITICAL"

        return "CRITICAL"