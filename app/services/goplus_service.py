"""
Módulo: Segurança - GoPlus Security
100% gratuito para uso básico, sem necessidade de API key.
Docs: https://docs.gopluslabs.io/reference/tokensecurity-using-get
"""
from typing import Optional

from app.config import settings
from app.models.schemas import DadosSeguranca, Rede
from app.utils.cache import cache_get, cache_set, chave_cache
from app.utils.http_client import APIClientError, get_json
from app.logging_config import get_logger

logger = get_logger(__name__)

# IDs de chain usados pela GoPlus API (padrão chainId numérico, exceto Solana)
CHAIN_IDS_EVM = {
    Rede.ETHEREUM: "1",
    Rede.BSC: "56",
    Rede.POLYGON: "137",
    Rede.ARBITRUM: "42161",
    Rede.BASE: "8453",
    Rede.AVALANCHE: "43114",
}


async def consultar_seguranca(endereco_contrato: str, rede: Rede) -> DadosSeguranca:
    """
    Consulta segurança do contrato. Solana usa endpoint dedicado,
    EVM usa o endpoint genérico com chain_id.
    """
    chave = chave_cache("goplus", rede.value, endereco_contrato)
    cacheado = await cache_get(chave)
    if cacheado:
        logger.info("cache_hit", fonte="goplus", contrato=endereco_contrato)
        return DadosSeguranca(**cacheado)

    if rede == Rede.SOLANA:
        resultado = await _consultar_solana(endereco_contrato)
    elif rede in CHAIN_IDS_EVM:
        resultado = await _consultar_evm(endereco_contrato, CHAIN_IDS_EVM[rede])
    else:
        logger.info("rede_sem_suporte_goplus", rede=rede.value)
        resultado = DadosSeguranca(dados_disponiveis=False)

    await cache_set(chave, resultado.model_dump())
    return resultado


async def _consultar_evm(endereco: str, chain_id: str) -> DadosSeguranca:
    url = f"{settings.goplus_api_url}/token_security/{chain_id}"
    try:
        data = await get_json(url, params={"contract_addresses": endereco.lower()}, fonte="goplus")
    except APIClientError as e:
        logger.error("goplus_falhou", erro=e.mensagem)
        return DadosSeguranca(dados_disponiveis=False)

    if not data or data.get("code") != 1:
        return DadosSeguranca(dados_disponiveis=False)

    resultado_token = (data.get("result") or {}).get(endereco.lower())
    if not resultado_token:
        return DadosSeguranca(dados_disponiveis=False)

    def flag(campo: str) -> Optional[bool]:
        valor = resultado_token.get(campo)
        if valor is None:
            return None
        return valor == "1"

    holders = resultado_token.get("holders", [])
    top_10_pct = None
    if holders:
        try:
            top_10 = holders[:10]
            top_10_pct = round(sum(float(h.get("percent", 0)) for h in top_10) * 100, 2)
        except (ValueError, TypeError):
            top_10_pct = None

    liquidez_travada_pct = None
    dex_info = resultado_token.get("dex", [])
    if dex_info:
        try:
            liquidez_travada_pct = round(
                max(float(d.get("liquidity_locked_percent", 0) or 0) for d in dex_info) * 100, 2
            )
        except (ValueError, TypeError):
            pass

    return DadosSeguranca(
        contrato_verificado=flag("is_open_source"),
        eh_honeypot=flag("is_honeypot"),
        ownership_renunciado=flag("can_take_back_ownership") == False if flag("can_take_back_ownership") is not None else None,
        tem_mint_authority=flag("is_mintable"),
        tem_freeze_authority=None,  # conceito específico de Solana
        eh_proxy_contract=flag("is_proxy"),
        liquidez_travada_pct=liquidez_travada_pct,
        taxa_compra_pct=_to_pct(resultado_token.get("buy_tax")),
        taxa_venda_pct=_to_pct(resultado_token.get("sell_tax")),
        top_10_holders_pct=top_10_pct,
        total_holders=_to_int(resultado_token.get("holder_count")),
        eh_blacklistavel=flag("is_blacklisted"),
        dados_disponiveis=True,
    )


async def _consultar_solana(endereco_mint: str) -> DadosSeguranca:
    url = f"{settings.goplus_api_url}/solana/token_security"
    try:
        data = await get_json(url, params={"contract_addresses": endereco_mint}, fonte="goplus_solana")
    except APIClientError as e:
        logger.error("goplus_solana_falhou", erro=e.mensagem)
        return DadosSeguranca(dados_disponiveis=False)

    if not data or data.get("code") != 1:
        return DadosSeguranca(dados_disponiveis=False)

    resultado_token = (data.get("result") or {}).get(endereco_mint)
    if not resultado_token:
        return DadosSeguranca(dados_disponiveis=False)

    def flag(campo: str) -> Optional[bool]:
        valor = resultado_token.get(campo)
        if valor is None:
            return None
        return valor == "1"

    holders = resultado_token.get("holders", [])
    top_10_pct = None
    if holders:
        try:
            top_10 = holders[:10]
            top_10_pct = round(sum(float(h.get("percent", 0)) for h in top_10) * 100, 2)
        except (ValueError, TypeError):
            top_10_pct = None

    return DadosSeguranca(
        contrato_verificado=None,  # conceito não se aplica diretamente a Solana
        eh_honeypot=flag("is_honeypot") if "is_honeypot" in resultado_token else None,
        ownership_renunciado=None,
        tem_mint_authority=flag("mintable"),
        tem_freeze_authority=flag("freezable"),
        eh_proxy_contract=None,
        liquidez_travada_pct=None,
        taxa_compra_pct=None,
        taxa_venda_pct=None,
        top_10_holders_pct=top_10_pct,
        total_holders=_to_int(resultado_token.get("holder_count")),
        eh_blacklistavel=None,
        dados_disponiveis=True,
    )


def _to_pct(valor) -> Optional[float]:
    if valor is None:
        return None
    try:
        return round(float(valor) * 100, 2)
    except (ValueError, TypeError):
        return None


def _to_int(valor) -> Optional[int]:
    if valor is None:
        return None
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None
