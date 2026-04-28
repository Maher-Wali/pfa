from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agents.config import Settings


def build_llm(settings: Settings, temperature: float = 0.3) -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.anthropic_model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )


def invoke_text(llm: ChatAnthropic, system: str, user: str) -> str:
    response = llm.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=user),
        ]
    )

    return str(response.content).strip()