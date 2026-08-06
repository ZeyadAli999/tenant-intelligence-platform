"""Fail-closed provider construction."""

from app.config import Settings, get_settings
from services.llm.base import LLMProvider
from services.llm.groq_provider import GroqProvider


def build_llm_provider(settings: Settings | None = None) -> LLMProvider:
    resolved = settings or get_settings()
    return GroqProvider(resolved)
