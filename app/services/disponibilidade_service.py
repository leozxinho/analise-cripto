"""
Módulo: Exchange/Wallet Scanner
Verifica onde o token pode ser comprado, usando:
1. Lista de exchanges/DEXs já retornada pelo DEX Screener (gratuito, sem chamada extra)
2. Listas públicas de tokens das wallets (GitHub, gratuito)
3. CoinGecko (indica se está listado em exchanges centralizadas)
"""
from app.models.schemas import DadosMercado, DisponibilidadeCompra, Rede
from app.utils.cache import cache_get, cache_set, chave_cache
from app.utils.http_client import APIClientError, get_json
from app.logging_config import get_logger

logger = get_logger(__name__)

# Listas públicas de tokens suportados (gratuitas, mantidas no GitHub)
TRUST_WALLET_LIST_URL = (
    "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/{rede}/tokenlist.json"
)

MAPA_REDE_TRUSTWALLET = {
    Rede.ETHEREUM: "ethereum",
    Rede.BSC: "smartchain",
    Rede.POLYGON: "polygon",
    Rede.SOLANA: "solana",
    Rede.AVALANCHE: "avalanchec",
    Rede.ARBITRUM: "arbitrum",
    Rede.BASE: "base",
}

DEXS_QUE_INDICAM_WALLET_COMPATIVEL = {
    "raydium": ["Phantom", "Solflare"],
    "orca": ["Phantom", "Solflare"],
    "pumpfun": ["Phantom", "Solflare"],
    "uniswap": ["MetaMask", "Trust Wallet", "Coinbase Wallet"],
    "pancakeswap": ["Trust Wallet", "Binance Wallet", "MetaMask"],
    "pixswap": ["PixSwap"],
}


async def verificar_disponibilidade(
    endereco_contrato: str, rede: Rede, dados_mercado: DadosMercado
) -> DisponibilidadeCompra:
    chave = chave_cache("disponibilidade", rede.value, endereco_contrato)
    cacheado = await cache_get(chave)
    if cacheado:
        return DisponibilidadeCompra(**cacheado)

    dexs = list(dados_mercado.exchanges)

    wallets = set()
    for dex in dexs:
        dex_normalizado = dex.lower().replace(" ", "")
        for chave_dex, wallets_compativeis in DEXS_QUE_INDICAM_WALLET_COMPATIVEL.items():
            if chave_dex in dex_normalizado:
                wallets.update(wallets_compativeis)

    suportado_trust_wallet = await _verificar_trust_wallet(endereco_contrato, rede)
    if suportado_trust_wallet:
        wallets.add("Trust Wallet")

    # OKX Wallet e Bitget aceitam praticamente qualquer token via DEX integrado,
    # então listamos como disponível sempre que houver liquidez em DEX.
    if dados_mercado.liquidez_usd and dados_mercado.liquidez_usd > 0:
        wallets.add("OKX Wallet")

    resultado = DisponibilidadeCompra(
        wallets_descentralizadas=sorted(wallets),
        dexs=sorted(dexs),
        exchanges_centralizadas=[],  # exchanges centralizadas exigem listagem oficial; não inferimos sem confirmação
    )

    await cache_set(chave, resultado.model_dump(), ttl=600)
    return resultado


async def _verificar_trust_wallet(endereco_contrato: str, rede: Rede) -> bool:
    """Consulta a lista pública de tokens da Trust Wallet no GitHub (gratuita)."""
    slug_rede = MAPA_REDE_TRUSTWALLET.get(rede)
    if not slug_rede:
        return False

    url = TRUST_WALLET_LIST_URL.format(rede=slug_rede)
    try:
        data = await get_json(url, fonte="trustwallet_list")
    except APIClientError:
        return False

    if not data or "tokens" not in data:
        return False

    enderecos = {t.get("address", "").lower() for t in data["tokens"]}
    return endereco_contrato.lower() in enderecos
