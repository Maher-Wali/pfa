import numpy as np
import torch
from datasets import load_dataset
from sklearn.metrics import classification_report, recall_score
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
)

# ── Change this before each run: 1 → 2 → 3 → 4 ──────────────────────────────
PART = 2
# ─────────────────────────────────────────────────────────────────────────────

TOTAL_PARTS = 4
BASE_MODEL = "mental/mental-roberta-base"
DATASET_NAME = "vibhorag101/suicide_prediction_dataset_phr"
MAX_LENGTH = 512
BATCH_SIZE = 16
FREEZE_LAYERS = 8
CRISIS_WEIGHT = 3.0

# Part 1 loads the base model; subsequent parts load the previous part's output
MODEL_NAME = BASE_MODEL if PART == 1 else f"./output/part_{PART - 1}"
OUTPUT_DIR = f"./output/part_{PART}"

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)


def preprocess(batch):
    tokens = tokenizer(
        batch["text"],
        truncation=True,
        max_length=MAX_LENGTH,
        padding="max_length",
    )
    tokens["labels"] = [1 if label == "suicide" else 0 for label in batch["label"]]
    return tokens


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    crisis_recall = recall_score(labels, preds, pos_label=1)
    report = classification_report(labels, preds, target_names=["safe", "crisis"])
    print(f"\n{report}")
    return {"crisis_recall": crisis_recall}


class WeightedLossTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        weights = torch.tensor([1.0, CRISIS_WEIGHT], device=outputs.logits.device)
        loss = torch.nn.functional.cross_entropy(outputs.logits, labels, weight=weights)
        return (loss, outputs) if return_outputs else loss


def freeze_bottom_layers(model, n_layers):
    for i, layer in enumerate(model.roberta.encoder.layer):
        if i < n_layers:
            for param in layer.parameters():
                param.requires_grad = False


def main():
    print(f"\n{'='*50}")
    print(f"  Training part {PART} / {TOTAL_PARTS}")
    print(f"  Loading model from: {MODEL_NAME}")
    print(f"  Saving to:          {OUTPUT_DIR}")
    print(f"{'='*50}\n")

    raw = load_dataset(DATASET_NAME)

    split = raw["train"].train_test_split(test_size=0.1, seed=42)
    dataset = {
        "train": split["train"],
        "validation": split["test"],
        "test": raw["test"],
    }

    remove_cols = dataset["train"].column_names
    tokenized = {
        s: ds.map(preprocess, batched=True, remove_columns=remove_cols)
        for s, ds in dataset.items()
    }

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=2,
        id2label={0: "safe", 1: "crisis"},
        label2id={"safe": 0, "crisis": 1},
        ignore_mismatched_sizes=True,
    )
    # Only freeze on part 1 — in later parts the head is already trained
    if PART == 1:
        freeze_bottom_layers(model, FREEZE_LAYERS)

    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=1,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        eval_strategy="epoch",
        save_strategy="epoch",
        fp16=torch.cuda.is_available(),
        logging_steps=100,
        report_to="none",
        save_total_limit=1,
        save_only_model=True,
    )

    trainer = WeightedLossTrainer(
        model=model,
        args=args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        compute_metrics=compute_metrics,
    )

    trainer.train()

    # Full test set evaluation only on the last part
    if PART == TOTAL_PARTS:
        print("\n--- Final test set evaluation ---")
        trainer.evaluate(tokenized["test"])

    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"\nPart {PART} saved to {OUTPUT_DIR}")
    if PART < TOTAL_PARTS:
        print(f"Next: set PART = {PART + 1} and rerun.")
    else:
        print("Training complete. Load the model from ./output/part_4")


if __name__ == "__main__":
    main()
