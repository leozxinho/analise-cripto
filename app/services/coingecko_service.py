"""
Módulo: Comunidade - CoinGecko
Free tier generoso, chave de API opcional (Demo key aumenta limites).
Docs: https://docs.coingecko.com/reference/introduction
"""
from typing import Optional

from app.config import settings
from app.models.schemas import DadosComunidade
from app.utils.cache import cache_get, cache_set, chave_cache
from app.utils.http_client import APIClientError, get_json
from app.logging_config import get_logger

logger = get_logger(__name__)

PLATAFORMAS_COINGECKO = {
    "ethereum": "ethereum",
    "bsc": "binance-smart-chain",
    "polygon": "polygon-pos",
    "arbitrum": "arbitrum-one",
    "base": "base",
    "avalanche": "avalanche",
    "solana": "solana",
    "tron": "tron",
}


async def buscar_dados_comunidade(endereco_contrato: str, rede: str) -> DadosComunidade:
    chave = chave_cache("coingecko", rede, endereco_contrato)
    cacheado = await cache_get(chave)
    if cacheado:
        logger.info("cache_hit", fonte="coingecko", contrato=endereco_contrato)
        return DadosComunidade(**cacheado)

    plataforma = PLATAFORMAS_COINGECKO.get(rede)
    if not plataforma:
        return DadosComunidade()

    url = f"{settings.coingecko_api_url}/coins/{plataforma}/contract/{endereco_contrato}"
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    try:
        data = await get_json(url, headers=headers, fonte="coingecko")
    except APIClientError as e:
        logger.warning("coingecko_falhou", erro=e.mensagem)
        return DadosComunidade()

    if not data:
        return DadosComunidade()

    links = data.get("links", {}) or {}
    community_data = data.get("community_data", {}) or {}

    twitter_handle = links.get("twitter_screen_name")
    telegram_handle = links.get("telegram_channel_identifier")
    sites = [s for s in links.get("homepage", []) if s]

    seguidores = community_data.get("twitter_followers")

    score = calcular_score_comunidade(
        seguidores=seguidores,
        tem_telegram=bool(telegram_handle),
        tem_site=bool(sites),
    )

    resultado = DadosComunidade(
        twitter_url=f"https://x.com/{twitter_handle}" if twitter_handle else None,
        telegram_url=f"https://t.me/{telegram_handle}" if telegram_handle else None,
        discord_url=next(iter(links.get("chat_url", [])), None) if links.get("chat_url") else None,
        site_oficial=sites[0] if sites else None,
        twitter_seguidores=seguidores,
        score_comunidade=score,
    )

    await cache_set(chave, resultado.model_dump(), ttl=600)  # comunidade muda devagar, cache maior
    return resultado


def calcular_score_comunidade(
    seguidores: Optional[int], tem_telegram: bool, tem_site: bool
) -> float:
    """Heurística simples de 0-100 para força de comunidade, sem IA."""
    score = 0.0

    if seguidores:
        if seguidores >= 100_000:
            score += 50
        elif seguidores >= 20_000:
            score += 35
        elif seguidores >= 5_000:
            score += 20
        elif seguidores >= 1_000:
            score += 10
        else:
            score += 5

    if tem_telegram:
        score += 25
    if tem_site:
        score += 25

    return min(score, 100.0)
