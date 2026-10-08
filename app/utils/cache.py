"""
Cache em memória com TTL — substitui Redis para simplificar o deploy.
Suficiente para evitar chamadas repetidas às APIs externas numa janela de tempo.
"""
import json
import time
from typing import Any, Optional

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_cache: dict[str, tuple[Any, float]] = {}  # chave -> (valor, timestamp_expiry)


async def cache_get(chave: str) -> Optional[Any]:
    entrada = _cache.get(chave)
    if entrada is None:
        return None
    valor, expiry = entrada
    if time.monotonic() > expiry:
        del _cache[chave]
        return None
    return valor


async def cache_set(chave: str, valor: Any, ttl: int | None = None) -> None:
    ttl = ttl or settings.cache_ttl_seconds
    _cache[chave] = (valor, time.monotonic() + ttl)


def chave_cache(*partes: str) -> str:
    return "memecoin:" + ":".join(p.lower() for p in partes if p)
