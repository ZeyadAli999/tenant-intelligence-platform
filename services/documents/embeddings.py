"""Local-only embedding interface and FastEmbed implementation."""

from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

from fastembed import TextEmbedding

from app.config import Settings


class EmbeddingService(Protocol):
    model_name: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedService:
    dimension = 384

    def __init__(self, settings: Settings) -> None:
        if settings.embedding_dimension != self.dimension:
            raise ValueError("Embedding dimension does not match configured model")
        self.model_name = settings.embedding_model
        self.batch_size = settings.embedding_batch_size
        self.cache_dir = settings.embedding_cache_dir

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            vector.tolist()
            for vector in _model(self.model_name, self.cache_dir).embed(
                list(texts), batch_size=self.batch_size
            )
        ]


@lru_cache(maxsize=1)
def _model(model_name: str, cache_dir: str) -> TextEmbedding:
    return TextEmbedding(
        model_name=model_name, cache_dir=cache_dir, providers=["CPUExecutionProvider"]
    )
