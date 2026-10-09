"""
Módulo: AI Analyst Service
Gera análise de mercado em linguagem natural usando Claude Haiku com prompt caching.
"""
from anthropic import AsyncAnthropic

from app.config import settings
from app.logging_config import get_logger
from app.models.schemas import AnaliseCompleta

logger = get_logger(__name__)

_client: AsyncAnthropic | None = None

SYSTEM_PROMPT = (
    "Você é um analista especializado em criptomoedas e tokens recém-listados na Solana.\n"
    "Com base nos dados fornecidos, escreva uma análise direta em português com 3 a 4 frases.\n"
    "Seja objetivo: mencione os pontos mais relevantes como liquidez, volume, risco e distribuição.\n"
    "Termine SEMPRE com exatamente uma das linhas abaixo (sem texto adicional após ela):\n"
    "Sinal: 🟢 COMPRA\n"
    "Sinal: 🟡 AGUARDAR\n"
    "Sinal: 🔴 EVITAR"
)


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def _montar_prompt(analise: AnaliseCompleta) -> str:
    m = analise.mercado
    s = analise.seguranca
    sc = analise.score

    def fmt(v) -> str:
        return str(v) if v is not None else "N/D"

    linhas = [
        f"Token: {m.nome or analise.simbolo} ({m.simbolo})",
        f"Preço: ${fmt(m.preco_usd)}",
        f"Market Cap: ${fmt(m.market_cap)}",
        f"Liquidez: ${fmt(m.liquidez_usd)}",
        f"Volume 24h: ${fmt(m.volume_24h)}",
        f"Variação 24h: {fmt(m.variacao_preco_24h)}%",
        f"Compradores 24h: {fmt(m.compradores_24h)}",
        f"Vendedores 24h: {fmt(m.vendedores_24h)}",
        f"Idade do token: {fmt(m.idade_dias)} dias",
        f"Número de pools: {m.num_pools}",
        f"Exchanges: {', '.join(m.exchanges) or 'N/D'}",
        f"Classificação automática: {analise.classificacao.value}",
        f"Score geral: {sc.nota_final}/100",
        f"Score segurança: {sc.seguranca} | liquidez: {sc.liquidez} | volume: {sc.volume} | comunidade: {sc.comunidade} | tokenomics: {sc.tokenomics}",
    ]

    if s.dados_disponiveis:
        if s.eh_honeypot is not None:
            linhas.append(f"Honeypot: {'Sim ⚠️' if s.eh_honeypot else 'Não ✅'}")
        if s.contrato_verificado is not None:
            linhas.append(f"Contrato verificado: {'Sim' if s.contrato_verificado else 'Não'}")
        if s.ownership_renunciado is not None:
            linhas.append(f"Ownership renunciado: {'Sim' if s.ownership_renunciado else 'Não'}")
        if s.top_10_holders_pct is not None:
            linhas.append(f"Top 10 holders: {s.top_10_holders_pct}%")
        if s.liquidez_travada_pct is not None:
            linhas.append(f"Liquidez travada: {s.liquidez_travada_pct}%")
        if s.taxa_compra_pct is not None:
            linhas.append(f"Taxa compra: {s.taxa_compra_pct}%")
        if s.taxa_venda_pct is not None:
            linhas.append(f"Taxa venda: {s.taxa_venda_pct}%")
        if s.total_holders is not None:
            linhas.append(f"Total holders: {s.total_holders}")
    else:
        linhas.append("Dados de segurança: não disponíveis para esta rede")

    return "\n".join(linhas)


async def gerar_analise_ia(analise: AnaliseCompleta) -> str | None:
    """Retorna análise textual com sinal de compra/aguardar/evitar, ou None se API key ausente."""
    if not settings.anthropic_api_key:
        return None

    try:
        client = _get_client()
        prompt = _montar_prompt(analise)

        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=350,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        texto = response.content[0].text.strip()
        logger.info(
            "analise_ia_gerada",
            tokens_input=response.usage.input_tokens,
            tokens_output=response.usage.output_tokens,
            cache_creation=getattr(response.usage, "cache_creation_input_tokens", 0),
            cache_read=getattr(response.usage, "cache_read_input_tokens", 0),
        )
        return texto

    except Exception as e:
        logger.error("analise_ia_falhou", erro=str(e))
        return None
