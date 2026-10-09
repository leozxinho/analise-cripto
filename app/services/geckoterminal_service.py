"""
Módulo: GeckoTerminal
API gratuita e sem chave para trending pools e novos pools na Solana.
Docs: https://api.geckoterminal.com/api/v2
"""
from app.logging_config import get_logger
from app.utils.http_client import APIClientError, get_json

logger = get_logger(__name__)

GECKOTERMINAL_BASE = "https://api.geckoterminal.com/api/v2"
HEADERS = {"Accept": "application/json;version=20230302"}


def _extrair_enderecos(data: dict) -> list[str]:
    """Extrai endereços de token base a partir da resposta padrão do GeckoTerminal."""
    enderecos = []
    for item in data.get("data", []):
        rel = item.get("relationships", {})
        base_id = rel.get("base_token", {}).get("data", {}).get("id", "")
        # formato: "solana_<endereco>"
        if base_id.startswith("solana_"):
            endereco = base_id[len("solana_"):]
            if endereco:
                enderecos.append(endereco)
    return enderecos


async def buscar_trending_solana() -> list[str]:
    """Retorna endereços de tokens nos trending pools da Solana agora."""
    url = f"{GECKOTERMINAL_BASE}/networks/solana/trending_pools"
    try:
        data = await get_json(url, headers=HEADERS, fonte="geckoterminal_trending")
    except APIClientError as e:
        logger.warning("geckoterminal_trending_falhou", erro=e.mensagem)
        return []

    enderecos = _extrair_enderecos(data or {})
    logger.info("geckoterminal_trending_obtido", total=len(enderecos))
    return enderecos


async def buscar_novos_pools_solana() -> list[str]:
    """Retorna endereços de tokens em pools recém-criados na Solana."""
    url = f"{GECKOTERMINAL_BASE}/networks/solana/new_pools"
    try:
        data = await get_json(url, headers=HEADERS, fonte="geckoterminal_new")
    except APIClientError as e:
        logger.warning("geckoterminal_new_pools_falhou", erro=e.mensagem)
        return []

    enderecos = _extrair_enderecos(data or {})
    logger.info("geckoterminal_new_pools_obtido", total=len(enderecos))
    return enderecos
