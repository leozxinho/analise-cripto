"""
Módulo: Score Engine (100% baseado em regras, SEM IA)

Calcula score de 0-100 em 5 categorias e gera classificação final.
Toda a lógica é determinística e auditável — fácil de ajustar os pesos.
"""
from app.models.schemas import (
    Classificacao,
    DadosComunidade,
    DadosMercado,
    DadosSeguranca,
    ScoreDetalhado,
)


def calcular_score_liquidez(mercado: DadosMercado) -> int:
    """0-100. Liquidez é o fator #1 de risco de manipulação em memecoins."""
    liq = mercado.liquidez_usd or 0

    if liq >= 500_000:
        score = 95
    elif liq >= 250_000:
        score = 85
    elif liq >= 100_000:
        score = 70
    elif liq >= 50_000:
        score = 55
    elif liq >= 20_000:
        score = 35
    elif liq > 0:
        score = 15
    else:
        score = 0

    # Bônus: múltiplos pools indicam liquidez mais resiliente
    if mercado.num_pools >= 3:
        score = min(score + 5, 100)

    return score


def calcular_score_volume(mercado: DadosMercado) -> int:
    """0-100. Considera volume 24h em relação ao market cap (liquidez de giro)
    e consistência entre janelas de 1h/6h/24h."""
    volume_24h = mercado.volume_24h or 0
    market_cap = mercado.market_cap or mercado.fdv or 0

    if volume_24h == 0:
        return 0

    # Razão volume/mcap: ideal entre 5% e 50%. Muito acima pode ser pump artificial.
    score = 30
    if market_cap > 0:
        razao = volume_24h / market_cap
        if 0.05 <= razao <= 0.5:
            score = 80
        elif 0.5 < razao <= 1.5:
            score = 60  # alto, pode ser hype real ou manipulação
        elif razao > 1.5:
            score = 30  # suspeito de wash trading
        elif razao < 0.05:
            score = 40
    else:
        # sem market cap de referência, julga pelo volume absoluto
        if volume_24h >= 1_000_000:
            score = 75
        elif volume_24h >= 100_000:
            score = 55
        elif volume_24h >= 10_000:
            score = 35

    # Consistência: volume 1h/6h proporcional ao 24h sugere atividade real e contínua
    if mercado.volume_1h is not None and mercado.volume_1h > 0:
        score = min(score + 10, 100)

    # Compradores vs vendedores equilibrados é saudável
    compradores = mercado.compradores_24h or 0
    vendedores = mercado.vendedores_24h or 0
    if compradores + vendedores > 0:
        proporcao_compra = compradores / (compradores + vendedores)
        if 0.4 <= proporcao_compra <= 0.7:
            score = min(score + 10, 100)
        elif proporcao_compra > 0.85:
            score = max(score - 10, 0)  # quase só compras pode indicar bot/pump

    return min(score, 100)


def calcular_score_seguranca(seguranca: DadosSeguranca) -> int:
    """0-100. O mais crítico — detecta golpes."""
    if not seguranca.dados_disponiveis:
        return 40  # neutro-baixo: não conseguimos verificar, não assumimos o melhor caso

    score = 50  # base neutra

    if seguranca.eh_honeypot is True:
        return 0  # honeypot é desqualificante, ignora o resto
    if seguranca.eh_honeypot is False:
        score += 20

    if seguranca.contrato_verificado is True:
        score += 10
    elif seguranca.contrato_verificado is False:
        score -= 15

    if seguranca.ownership_renunciado is True:
        score += 10

    if seguranca.tem_mint_authority is True:
        score -= 15  # dev pode criar tokens infinitos
    elif seguranca.tem_mint_authority is False:
        score += 5

    if seguranca.tem_freeze_authority is True:
        score -= 10  # dev pode congelar carteiras (comum em scams Solana)

    if seguranca.eh_proxy_contract is True:
        score -= 10  # contrato pode ser alterado depois

    if seguranca.eh_blacklistavel is True:
        score -= 10

    if seguranca.liquidez_travada_pct is not None:
        if seguranca.liquidez_travada_pct >= 80:
            score += 15
        elif seguranca.liquidez_travada_pct >= 50:
            score += 5
        else:
            score -= 10

    if seguranca.taxa_compra_pct is not None and seguranca.taxa_venda_pct is not None:
        taxa_total = seguranca.taxa_compra_pct + seguranca.taxa_venda_pct
        if taxa_total > 20:
            score -= 20  # taxas abusivas, padrão de scam
        elif taxa_total > 10:
            score -= 10

    if seguranca.top_10_holders_pct is not None:
        if seguranca.top_10_holders_pct >= 70:
            score -= 20  # extremamente concentrado
        elif seguranca.top_10_holders_pct >= 50:
            score -= 10
        elif seguranca.top_10_holders_pct <= 20:
            score += 10

    return max(0, min(score, 100))


def calcular_score_comunidade(comunidade: DadosComunidade) -> int:
    """0-100. Usa o score heurístico já calculado no módulo de comunidade."""
    if comunidade.score_comunidade is None:
        return 30  # sem dados, score conservador
    return int(comunidade.score_comunidade)


def calcular_score_tokenomics(mercado: DadosMercado, seguranca: DadosSeguranca) -> int:
    """0-100. Combina idade do token, holders e dados de supply disponíveis."""
    score = 40  # base

    if mercado.idade_dias is not None:
        if mercado.idade_dias >= 180:
            score += 25
        elif mercado.idade_dias >= 30:
            score += 15
        elif mercado.idade_dias >= 7:
            score += 5
        elif mercado.idade_dias < 1:
            score -= 15  # token recém-criado, alto risco

    if seguranca.total_holders is not None:
        if seguranca.total_holders >= 10_000:
            score += 20
        elif seguranca.total_holders >= 1_000:
            score += 10
        elif seguranca.total_holders >= 100:
            score += 5
        else:
            score -= 10

    return max(0, min(score, 100))


def calcular_score_geral(
    mercado: DadosMercado,
    seguranca: DadosSeguranca,
    comunidade: DadosComunidade,
) -> ScoreDetalhado:
    """
    Pesos por categoria — segurança e liquidez pesam mais por serem
    os principais indicadores de golpe/rug pull em memecoins.
    """
    s_seguranca = calcular_score_seguranca(seguranca)
    s_liquidez = calcular_score_liquidez(mercado)
    s_comunidade = calcular_score_comunidade(comunidade)
    s_volume = calcular_score_volume(mercado)
    s_tokenomics = calcular_score_tokenomics(mercado, seguranca)

    PESOS = {
        "seguranca": 0.35,
        "liquidez": 0.25,
        "volume": 0.15,
        "comunidade": 0.10,
        "tokenomics": 0.15,
    }

    nota_final = (
        s_seguranca * PESOS["seguranca"]
        + s_liquidez * PESOS["liquidez"]
        + s_volume * PESOS["volume"]
        + s_comunidade * PESOS["comunidade"]
        + s_tokenomics * PESOS["tokenomics"]
    )

    # Honeypot zera a nota geral independente do resto
    if seguranca.eh_honeypot is True:
        nota_final = 0

    return ScoreDetalhado(
        seguranca=s_seguranca,
        liquidez=s_liquidez,
        comunidade=s_comunidade,
        volume=s_volume,
        tokenomics=s_tokenomics,
        nota_final=round(nota_final),
    )


def classificar(score: ScoreDetalhado, seguranca: DadosSeguranca, mercado: DadosMercado) -> Classificacao:
    """Determina a classificação final baseada em regras claras."""

    # Casos eliminatórios de golpe, independente da nota
    if seguranca.eh_honeypot is True:
        return Classificacao.POSSIVEL_GOLPE

    if (
        seguranca.top_10_holders_pct is not None
        and seguranca.top_10_holders_pct >= 80
        and (mercado.liquidez_usd or 0) < 20_000
    ):
        return Classificacao.POSSIVEL_GOLPE

    nota = score.nota_final

    if nota >= 85:
        return Classificacao.MUITO_PROMISSORA
    elif nota >= 70:
        return Classificacao.PROMISSORA
    elif nota >= 50:
        return Classificacao.VALE_ACOMPANHAR
    elif nota >= 30:
        return Classificacao.ALTO_RISCO
    else:
        return Classificacao.NAO_RECOMENDADA
