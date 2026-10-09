"""
Módulo: Token Analyzer (orquestrador principal)

Recebe a query do usuário (símbolo ou contrato), detecta o tipo,
consulta todas as fontes em paralelo, e monta a AnaliseCompleta final.
"""
import asyncio
import re

from app.models.schemas import (
    AnaliseCompleta,
    DadosComunidade,
    DadosMercado,
    DadosSeguranca,
    DisponibilidadeCompra,
    Rede,
)
from app.services import (
    coingecko_service,
    dexscreener_service,
    disponibilidade_service,
    goplus_service,
)
from app.services.coingecko_service import calcular_score_comunidade
from app.services.recommendation_engine import (
    determinar_nivel_risco,
    gerar_parecer,
    gerar_recomendacao,
)
from app.services.score_engine import calcular_score_geral, classificar
from app.services.ai_analyst_service import gerar_analise_ia
from app.logging_config import get_logger

logger = get_logger(__name__)

# Detecta endereços de contrato: EVM (0x...) ou Solana (base58, 32-44 chars)
REGEX_CONTRATO_EVM = re.compile(r"^0x[a-fA-F0-9]{40}$")
REGEX_CONTRATO_SOLANA = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def eh_endereco_contrato(texto: str) -> bool:
    texto = texto.strip()
    return bool(REGEX_CONTRATO_EVM.match(texto) or REGEX_CONTRATO_SOLANA.match(texto))


async def analisar_token(query: str) -> AnaliseCompleta:
    """
    Ponto de entrada principal. Recebe símbolo, nome ou endereço de contrato
    e retorna a análise completa.
    """
    query = query.strip()
    erros: list[str] = []

    logger.info("iniciando_analise", query=query)

    # 1. Buscar dados de mercado (DEX Screener)
    if eh_endereco_contrato(query):
        mercado = await dexscreener_service.buscar_por_contrato(query)
        contrato = query
    else:
        mercado = await dexscreener_service.buscar_por_simbolo(query)
        contrato = mercado.pair_address if mercado else None

    if mercado is None:
        logger.warning("token_nao_encontrado", query=query)
        return _analise_vazia(query, erro="Token não encontrado no DEX Screener. Verifique o símbolo ou contrato informado.")

    # O endereço real do token (base token), não o par
    contrato_real = contrato or query

    # 2. Consultar segurança e comunidade EM PARALELO (mais rápido)
    resultado_seguranca, resultado_comunidade = await asyncio.gather(
        _consultar_seguranca_seguro(contrato_real, mercado.rede),
        _consultar_comunidade_seguro(contrato_real, mercado.rede),
        return_exceptions=False,
    )

    # Se CoinGecko não indexou o token ainda, usa links sociais do DEX Screener
    if not resultado_comunidade.twitter_url and (mercado.twitter_url or mercado.telegram_url or mercado.site_oficial):
        resultado_comunidade = DadosComunidade(
            twitter_url=mercado.twitter_url,
            telegram_url=mercado.telegram_url,
            site_oficial=mercado.site_oficial,
            score_comunidade=calcular_score_comunidade(
                seguidores=None,
                tem_telegram=bool(mercado.telegram_url),
                tem_site=bool(mercado.site_oficial),
            ),
        )

    # 3. Disponibilidade de compra (depende dos dados de mercado já obtidos)
    disponibilidade = await disponibilidade_service.verificar_disponibilidade(
        contrato_real, mercado.rede, mercado
    )

    # 4. Calcular score (sem IA, só regras)
    score = calcular_score_geral(mercado, resultado_seguranca, resultado_comunidade)
    classificacao = classificar(score, resultado_seguranca, mercado)

    # 5. Gerar parecer e recomendação (templates condicionais, sem IA)
    parecer = gerar_parecer(mercado, resultado_seguranca, resultado_comunidade, score, classificacao)
    recomendacao = gerar_recomendacao(classificacao, score)
    nivel_risco = determinar_nivel_risco(classificacao)

    # 6. Análise IA opcional (Claude Haiku) — só se API key configurada
    analise_ia = await gerar_analise_ia(AnaliseCompleta(
        query_original=query,
        nome=mercado.nome,
        simbolo=mercado.simbolo,
        rede=mercado.rede,
        contrato=contrato_real,
        mercado=mercado,
        seguranca=resultado_seguranca,
        comunidade=resultado_comunidade,
        disponibilidade=DisponibilidadeCompra(),
        score=score,
        classificacao=classificacao,
        parecer=parecer,
        recomendacao=recomendacao,
        nivel_risco=nivel_risco,
    ))

    logger.info(
        "analise_concluida",
        query=query,
        simbolo=mercado.simbolo,
        nota_final=score.nota_final,
        classificacao=classificacao.value,
    )

    return AnaliseCompleta(
        query_original=query,
        nome=mercado.nome,
        simbolo=mercado.simbolo,
        rede=mercado.rede,
        contrato=contrato_real,
        mercado=mercado,
        seguranca=resultado_seguranca,
        comunidade=resultado_comunidade,
        disponibilidade=disponibilidade,
        score=score,
        classificacao=classificacao,
        parecer=parecer,
        recomendacao=recomendacao,
        nivel_risco=nivel_risco,
        analise_ia=analise_ia,
        erros=erros,
    )


async def _consultar_seguranca_seguro(contrato: str, rede: Rede) -> DadosSeguranca:
    try:
        return await goplus_service.consultar_seguranca(contrato, rede)
    except Exception as e:
        logger.error("falha_consulta_seguranca", erro=str(e))
        return DadosSeguranca(dados_disponiveis=False)


async def _consultar_comunidade_seguro(contrato: str, rede: Rede) -> DadosComunidade:
    try:
        return await coingecko_service.buscar_dados_comunidade(contrato, rede.value)
    except Exception as e:
        logger.error("falha_consulta_comunidade", erro=str(e))
        return DadosComunidade()


def _analise_vazia(query: str, erro: str) -> AnaliseCompleta:
    """Retorna uma análise 'vazia' quando o token não é encontrado, sem quebrar o fluxo."""
    from app.models.schemas import Classificacao, ScoreDetalhado

    return AnaliseCompleta(
        query_original=query,
        mercado=DadosMercado(),
        seguranca=DadosSeguranca(dados_disponiveis=False),
        comunidade=DadosComunidade(),
        disponibilidade=DisponibilidadeCompra(),
        score=ScoreDetalhado(),
        classificacao=Classificacao.NAO_RECOMENDADA,
        parecer="Não foi possível encontrar dados para este token.",
        recomendacao="Verifique se o símbolo ou contrato está correto e tente novamente.",
        nivel_risco="Indeterminado",
        erros=[erro],
    )
