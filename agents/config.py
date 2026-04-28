from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    anthropic_model: str = "claude-3-5-sonnet-latest"

    db1_index_name: str = "db1"
    db2_index_name: str = "db2"

    classifier_model_name: str = "maherwali/mental-safety-classifier"

    embedding_model_name: str = "BAAI/bge-base-en-v1.5"
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    top_k_docs: int = 5
    classify_every_agent2_messages: int = 4

    sqlite_db_path: str = "data/conversations.sqlite3"


def get_settings() -> Settings:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing in your .env file.")

    return Settings(
        anthropic_api_key=api_key,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),

        db1_index_name=os.getenv("DB1_INDEX_NAME", "db1"),
        db2_index_name=os.getenv("DB2_INDEX_NAME", "db2"),

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
        classify_every_agent2_messages=int(
            os.getenv("CLASSIFY_EVERY_AGENT2_MESSAGES", "4")
        ),

        sqlite_db_path=os.getenv(
            "SQLITE_DB_PATH",
            "data/conversations.sqlite3",
        ),
    )