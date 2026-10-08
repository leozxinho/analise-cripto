"""
Módulo: Monitor Service

A cada varredura (5 min):
1. Busca tokens boosted/trending Solana no DEX Screener
2. Pré-filtra por idade (listados nos últimos 15 min, com buffer do intervalo)
3. Descarta tokens já notificados (chave no Redis com TTL de 24h)
4. Roda análise completa (score, segurança, liquidez)
5. Aplica filtros de qualidade mínima
6. Envia alerta via CallMeBot
"""
import asyncio

from app.config import settings
from app.logging_config import get_logger
from app.models.schemas import Classificacao
from app.services import dexscreener_service
from app.services.telegram_service import enviar_mensagem
from app.services.response_formatter import formatar_resposta_whatsapp
from app.services.token_analyzer import analisar_token
from app.utils.cache import get_redis
from app.utils.http_client import APIClientError, get_json

logger = get_logger(__name__)

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
SCAN_INTERVAL_SECONDS = 300       # 5 minutos
MAX_TOKEN_AGE_MINUTES = 15        # janela com buffer do intervalo de varredura
SEEN_TOKEN_TTL_SECONDS = 86_400   # 24h — evita re-notificar o mesmo token

MIN_SCORE = 35
MIN_LIQUIDEZ_USD = 5_000
CLASSIFICACOES_BLOQUEADAS = {Classificacao.POSSIVEL_GOLPE, Classificacao.NAO_RECOMENDADA}


async def _ja_notificado(token_address: str) -> bool:
    redis = await get_redis()
    return bool(await redis.exists(f"memecoin:notificado:{token_address.lower()}"))


async def _marcar_notificado(token_address: str) -> None:
    redis = await get_redis()
    await redis.set(f"memecoin:notificado:{token_address.lower()}", "1", ex=SEEN_TOKEN_TTL_SECONDS)


async def _buscar_boosted_solana() -> list[str]:
    """Retorna endereços de tokens Solana que estão boosted/trending agora."""
    try:
        data = await get_json(DEXSCREENER_BOOSTS_URL, fonte="dexscreener_boosts")
    except APIClientError as e:
        logger.error("boosts_fetch_falhou", erro=e.mensagem)
        return []

    if not isinstance(data, list):
        return []

    return [
        item["tokenAddress"]
        for item in data
        if isinstance(item, dict)
        and item.get("chainId") == "solana"
        and item.get("tokenAddress")
    ]


async def _token_e_recente(token_address: str) -> bool:
    """Verifica a idade buscando apenas os dados do DEX Screener (sem análise completa)."""
    dados = await dexscreener_service.buscar_por_contrato(token_address)
    if dados is None or dados.idade_dias is None:
        return False
    max_dias = MAX_TOKEN_AGE_MINUTES / 1440
    return dados.idade_dias <= max_dias


async def _processar_token(token_address: str) -> None:
    if await _ja_notificado(token_address):
        return

    if not await _token_e_recente(token_address):
        return

    analise = await analisar_token(token_address)

    # Descarta e marca para não re-verificar tokens que não passam nos filtros
    if analise.classificacao in CLASSIFICACOES_BLOQUEADAS:
        logger.info("token_descartado_classificacao", token=token_address, classificacao=analise.classificacao.value)
        await _marcar_notificado(token_address)
        return

    if analise.score.nota_final < MIN_SCORE:
        logger.info("token_descartado_score", token=token_address, score=analise.score.nota_final)
        await _marcar_notificado(token_address)
        return

    if (analise.mercado.liquidez_usd or 0) < MIN_LIQUIDEZ_USD:
        logger.info("token_descartado_liquidez", token=token_address, liquidez=analise.mercado.liquidez_usd)
        await _marcar_notificado(token_address)
        return

    mensagem = "🆕 *Novo token detectado na Solana!*\n\n" + formatar_resposta_whatsapp(analise)
    await enviar_mensagem(mensagem)
    await _marcar_notificado(token_address)
    logger.info(
        "token_notificado",
        token=token_address,
        simbolo=analise.simbolo,
        score=analise.score.nota_final,
        classificacao=analise.classificacao.value,
    )


async def executar_varredura() -> None:
    logger.info("varredura_iniciada")
    tokens = await _buscar_boosted_solana()
    logger.info("tokens_boosted_encontrados", total=len(tokens))

    for token_address in tokens:
        try:
            await _processar_token(token_address)
        except Exception as e:
            logger.error("erro_processando_token", token=token_address, erro=str(e))

    logger.info("varredura_concluida", tokens_verificados=len(tokens))


async def loop_monitoramento() -> None:
    """Loop infinito executado em background pelo FastAPI lifespan."""
    logger.info("monitor_iniciado", intervalo_segundos=SCAN_INTERVAL_SECONDS)
    while True:
        await executar_varredura()
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)
