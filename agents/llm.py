from __future__ import annotations

from openai import OpenAI

from agents.config import Settings

# --- Anthropic / Claude (uncomment to switch backend) ---
# from langchain_anthropic import ChatAnthropic
# from langchain_core.messages import HumanMessage, SystemMessage
#
# def build_llm(settings: Settings, temperature: float = 0.3) -> ChatAnthropic:
#     return ChatAnthropic(
#         model=settings.anthropic_model,
#         anthropic_api_key=settings.anthropic_api_key,
#         temperature=temperature,
#         timeout=60,
#         max_retries=2,
#     )
#
# def invoke_text(llm: ChatAnthropic, system: str, user: str) -> str:
#     response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
#     return str(response.content).strip()
# --------------------------------------------------------


class LLMClient:
    def __init__(self, settings: Settings, temperature: float = 0.3):
        self.client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
        self.temperature = temperature
        self.model = settings.llm_model
        if not self.model:
            self.model = self.client.models.list().data[0].id
            print(f"LM Studio model: {self.model}")


def build_llm(settings: Settings, temperature: float = 0.3) -> LLMClient:
    return LLMClient(settings, temperature)


def invoke_text(llm: LLMClient, system: str, user: str, max_tokens: int | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    kwargs = dict(model=llm.model, messages=messages, temperature=llm.temperature)
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    response = llm.client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""
