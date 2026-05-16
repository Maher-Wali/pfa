from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    # --- LM Studio (active backend) ---
    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str = ""

    # --- Anthropic / Claude (uncomment fields + get_settings() lines to switch) ---
    # anthropic_api_key: str = ""
    # anthropic_model: str = "claude-3-5-sonnet-latest"

    db1_index_name: str = "mental-health-clinical"
    db2_index_name: str = "mental-health-therapy"

    classifier_model_name: str = "maherwali/mental-safety-classifier"

    embedding_model_name: str = "BAAI/bge-base-en-v1.5"
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    top_k_docs: int = 5
    classify_every_n_turns: int = 4

    sqlite_db_path: str = "data/conversations.sqlite3"


def get_settings() -> Settings:
    return Settings(
        # --- LM Studio ---
        llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:1234/v1"),
        llm_api_key=os.getenv("LLM_API_KEY", "lm-studio"),
        llm_model=os.getenv("LLM_MODEL", ""),

        # --- Anthropic (uncomment to switch) ---
        # anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        # anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),

        db1_index_name=os.getenv("DB1_INDEX_NAME", "mental-health-clinical"),
        db2_index_name=os.getenv("DB2_INDEX_NAME", "mental-health-therapy"),

        classifier_model_name=os.getenv(
            "CLASSIFIER_MODEL_NAME",
            "maherwali/mental-safety-classifier",
        ),

        embedding_model_name=os.getenv(
            "EMBEDDING_MODEL_NAME",
            "BAAI/bge-base-en-v1.5",
        ),
        reranker_model_name=os.getenv(
            "RERANKER_MODEL_NAME",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        ),

        top_k_docs=int(os.getenv("TOP_K_DOCS", "5")),
        classify_every_n_turns=int(os.getenv("CLASSIFY_EVERY_N_TURNS", "4")),

        sqlite_db_path=os.getenv(
            "SQLITE_DB_PATH",
            "data/conversations.sqlite3",
        ),
    )
