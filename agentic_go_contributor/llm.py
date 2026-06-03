import os

from langchain_openai import ChatOpenAI


DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "1024"))


def get_llm(model: str = DEFAULT_MODEL) -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        model=model,
        temperature=0.1,
        max_tokens=MAX_TOKENS,
    )
