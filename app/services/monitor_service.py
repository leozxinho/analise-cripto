"""
Módulo: Monitor Service

A cada varredura (5 min):
1. Busca tokens boosted/trending Solana no DEX Screener
2. Pré-filtra por idade (listados nos últimos 15 min, com buffer do intervalo)
3. Descarta tokens já notificados (set em memória, resetado a cada restart)
4. Roda análise completa (score, segurança, liquidez)
5. Aplica filtros de qualidade mínima
6. Envia alerta via Telegram
"""
import asyncio

from app.logging_config import get_logger
from app.models.schemas import Classificacao
from app.services import dexscreener_service
from app.services.geckoterminal_service import buscar_novos_pools_solana, buscar_trending_solana
from app.services.telegram_service import enviar_mensagem
from app.services.response_formatter import formatar_resposta_whatsapp
from app.services.token_analyzer import analisar_token
from app.utils.http_client import APIClientError, get_json

logger = get_logger(__name__)

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
SCAN_INTERVAL_SECONDS = 300
MAX_TOKEN_AGE_MINUTES = 15

MIN_SCORE = 35
MIN_LIQUIDEZ_USD = 5_000
CLASSIFICACOES_BLOQUEADAS = {Classificacao.POSSIVEL_GOLPE, Classificacao.NAO_RECOMENDADA}

# Set em memória — sem dependência de Redis
_tokens_notificados: set[str] = set()


def _ja_notificado(token_address: str) -> bool:
    return token_address.lower() in _tokens_notificados


def _marcar_notificado(token_address: str) -> None:
    _tokens_notificados.add(token_address.lower())


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


async def _buscar_todos_candidatos() -> list[str]:
    """Coleta tokens das três fontes em paralelo e retorna lista deduplicada."""
    boosts, trending, novos = await asyncio.gather(
        _buscar_boosted_solana(),
        buscar_trending_solana(),
        buscar_novos_pools_solana(),
        return_exceptions=True,
    )

    vistos: set[str] = set()
    candidatos: list[str] = []

    for lista in (boosts, trending, novos):
        if isinstance(lista, Exception):
            logger.error("fonte_falhou", erro=str(lista))
            continue
        for addr in lista:
            chave = addr.lower()
            if chave not in vistos:
                vistos.add(chave)
                candidatos.append(addr)

    logger.info(
        "candidatos_coletados",
        boosts=len(boosts) if not isinstance(boosts, Exception) else 0,
        trending=len(trending) if not isinstance(trending, Exception) else 0,
        novos=len(novos) if not isinstance(novos, Exception) else 0,
        total_deduplicado=len(candidatos),
    )
    return candidatos


async def _token_e_recente(token_address: str) -> bool:
    """Verifica a idade buscando apenas os dados do DEX Screener (sem análise completa)."""
    dados = await dexscreener_service.buscar_por_contrato(token_address)
    if dados is None or dados.idade_dias is None:
        return False
    return dados.idade_dias <= (MAX_TOKEN_AGE_MINUTES / 1440)


async def _processar_token(token_address: str) -> None:
    if _ja_notificado(token_address):
        return

    if not await _token_e_recente(token_address):
        _marcar_notificado(token_address)
        return

    analise = await analisar_token(token_address)

    if analise.classificacao in CLASSIFICACOES_BLOQUEADAS:
        logger.info("token_descartado_classificacao", token=token_address, classificacao=analise.classificacao.value)
        _marcar_notificado(token_address)
        return

    if analise.score.nota_final < MIN_SCORE:
        logger.info("token_descartado_score", token=token_address, score=analise.score.nota_final)
        _marcar_notificado(token_address)
        return

    if (analise.mercado.liquidez_usd or 0) < MIN_LIQUIDEZ_USD:
        logger.info("token_descartado_liquidez", token=token_address, liquidez=analise.mercado.liquidez_usd)
        _marcar_notificado(token_address)
        return

    mensagem = "🆕 *Novo token detectado na Solana!*\n\n" + formatar_resposta_whatsapp(analise)
    await enviar_mensagem(mensagem)

    if analise.contrato:
        await enviar_mensagem(f"📋 *Contrato:*\n`{analise.contrato}`")

    _marcar_notificado(token_address)
    logger.info(
        "token_notificado",
        token=token_address,
        simbolo=analise.simbolo,
        score=analise.score.nota_final,
        classificacao=analise.classificacao.value,
    )


async def executar_varredura() -> None:
    logger.info("varredura_iniciada")
    tokens = await _buscar_todos_candidatos()

    for token_address in tokens:
        try:
            await _processar_token(token_address)
        except Exception as e:
            logger.error("erro_processando_token", token=token_address, erro=str(e))

    logger.info("varredura_concluida", tokens_verificados=len(tokens))


async def loop_monitoramento() -> None:
    logger.info("monitor_iniciado", intervalo_segundos=SCAN_INTERVAL_SECONDS)
    await asyncio.sleep(5)
    while True:
        try:
            await executar_varredura()
        except Exception as e:
            logger.error("varredura_falhou_inesperadamente", erro=str(e))
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


async def loop_heartbeat() -> None:
    """Envia mensagem no Telegram ao iniciar e depois a cada 2 horas."""
    await asyncio.sleep(5)  # aguarda o app subir completamente
    while True:
        await enviar_mensagem("✅ *Memecoin Analyzer ativo*\nMonitorando novos tokens Solana.")
        await asyncio.sleep(7_200)
