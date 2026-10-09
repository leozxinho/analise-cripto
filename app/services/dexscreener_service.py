"""
Módulo: Blockchain Scanner - DEX Screener
Fonte 100% gratuita, sem necessidade de API key.
Docs: https://docs.dexscreener.com/api/reference
"""
import time
from typing import Optional

from app.config import settings
from app.models.schemas import DadosMercado, Rede
from app.utils.cache import cache_get, cache_set, chave_cache
from app.utils.http_client import APIClientError, get_json
from app.logging_config import get_logger

logger = get_logger(__name__)

MAPA_REDES = {
    "ethereum": Rede.ETHEREUM,
    "solana": Rede.SOLANA,
    "bsc": Rede.BSC,
    "base": Rede.BASE,
    "arbitrum": Rede.ARBITRUM,
    "polygon": Rede.POLYGON,
    "avalanche": Rede.AVALANCHE,
    "sui": Rede.SUI,
    "tron": Rede.TRON,
}


async def buscar_por_contrato(endereco_contrato: str) -> Optional[DadosMercado]:
    """Busca dados de um token pelo endereço do contrato."""
    chave = chave_cache("dexscreener", "contrato", endereco_contrato)
    cacheado = await cache_get(chave)
    if cacheado:
        logger.info("cache_hit", fonte="dexscreener", contrato=endereco_contrato)
        return DadosMercado(**cacheado)

    url = f"{settings.dexscreener_api_url}/dex/tokens/{endereco_contrato}"
    try:
        data = await get_json(url, fonte="dexscreener")
    except APIClientError as e:
        logger.error("dexscreener_falhou", erro=e.mensagem)
        return None

    if not data or not data.get("pairs"):
        return None

    resultado = _parsear_melhor_par(data["pairs"])
    if resultado:
        await cache_set(chave, resultado.model_dump())
    return resultado


async def buscar_por_simbolo(simbolo: str) -> Optional[DadosMercado]:
    """Busca dados de um token pelo símbolo/nome (busca textual)."""
    chave = chave_cache("dexscreener", "simbolo", simbolo)
    cacheado = await cache_get(chave)
    if cacheado:
        logger.info("cache_hit", fonte="dexscreener", simbolo=simbolo)
        return DadosMercado(**cacheado)

    url = f"{settings.dexscreener_api_url}/dex/search"
    try:
        data = await get_json(url, params={"q": simbolo}, fonte="dexscreener")
    except APIClientError as e:
        logger.error("dexscreener_falhou", erro=e.mensagem)
        return None

    if not data or not data.get("pairs"):
        return None

    resultado = _parsear_melhor_par(data["pairs"])
    if resultado:
        await cache_set(chave, resultado.model_dump())
    return resultado


def _parsear_melhor_par(pairs: list[dict]) -> Optional[DadosMercado]:
    """
    O DEX Screener retorna vários pares (pools). Escolhemos o de maior liquidez,
    que normalmente é o mais confiável para análise.
    """
    if not pairs:
        return None

    pares_validos = [p for p in pairs if p.get("liquidity", {}).get("usd") is not None]
    if not pares_validos:
        pares_validos = pairs

    melhor_par = max(
        pares_validos,
        key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0,
    )

    todos_pares_mesmo_token = [
        p for p in pairs
        if p.get("baseToken", {}).get("address") == melhor_par.get("baseToken", {}).get("address")
    ]
    exchanges = list({p.get("dexId", "").title() for p in todos_pares_mesmo_token if p.get("dexId")})

    idade_dias = None
    if melhor_par.get("pairCreatedAt"):
        criado_em_ms = melhor_par["pairCreatedAt"]
        idade_segundos = time.time() - (criado_em_ms / 1000)
        idade_dias = round(idade_segundos / 86400, 2)

    rede_str = melhor_par.get("chainId", "").lower()
    rede = MAPA_REDES.get(rede_str, Rede.DESCONHECIDA)

    volume = melhor_par.get("volume", {}) or {}
    txns_24h = melhor_par.get("txns", {}).get("h24", {}) or {}
    price_change = melhor_par.get("priceChange", {}) or {}
    liquidity = melhor_par.get("liquidity", {}) or {}

    info = melhor_par.get("info", {}) or {}
    socials = info.get("socials", []) or []
    websites = info.get("websites", []) or []

    twitter_url = next((s.get("url") for s in socials if s.get("type") == "twitter"), None)
    telegram_url = next((s.get("url") for s in socials if s.get("type") == "telegram"), None)
    site_oficial = next((w.get("url") for w in websites if w.get("url")), None)

    return DadosMercado(
        preco_usd=_to_float(melhor_par.get("priceUsd")),
        market_cap=_to_float(melhor_par.get("marketCap")),
        fdv=_to_float(melhor_par.get("fdv")),
        liquidez_usd=_to_float(liquidity.get("usd")),
        volume_24h=_to_float(volume.get("h24")),
        volume_6h=_to_float(volume.get("h6")),
        volume_1h=_to_float(volume.get("h1")),
        variacao_preco_24h=_to_float(price_change.get("h24")),
        compradores_24h=txns_24h.get("buys"),
        vendedores_24h=txns_24h.get("sells"),
        idade_dias=idade_dias,
        num_pools=len(todos_pares_mesmo_token),
        exchanges=exchanges,
        pair_address=melhor_par.get("pairAddress"),
        rede=rede,
        nome=melhor_par.get("baseToken", {}).get("name"),
        simbolo=melhor_par.get("baseToken", {}).get("symbol"),
        url_dexscreener=melhor_par.get("url"),
        twitter_url=twitter_url,
        telegram_url=telegram_url,
        site_oficial=site_oficial,
    )


def _to_float(valor) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None
