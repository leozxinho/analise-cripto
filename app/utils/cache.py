"""
Cache em Redis para evitar consultas repetidas às APIs externas
e não estourar os limites gratuitos de requisições.
"""
import json
from typing import Any, Optional

import redis.asyncio as redis

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def cache_get(chave: str) -> Optional[Any]:
    try:
        client = await get_redis()
        valor = await client.get(chave)
        if valor is None:
            return None
        return json.loads(valor)
    except Exception as e:
        logger.warning("cache_get_falhou", chave=chave, erro=str(e))
        return None


async def cache_set(chave: str, valor: Any, ttl: int | None = None) -> None:
    try:
        client = await get_redis()
        ttl = ttl or settings.cache_ttl_seconds
        await client.set(chave, json.dumps(valor, default=str), ex=ttl)
    except Exception as e:
        logger.warning("cache_set_falhou", chave=chave, erro=str(e))


def chave_cache(*partes: str) -> str:
    """Monta uma chave de cache padronizada: 'memecoin:dexscreener:0x123...'"""
    return "memecoin:" + ":".join(p.lower() for p in partes if p)
