"""
Módulo: Recommendation Engine (100% baseado em regras, SEM IA)

Gera o parecer textual e a recomendação de compra usando templates
condicionais — não é um texto fixo único, mas combina trechos
de acordo com os dados reais, dando a sensação de análise contextual.
"""
from app.models.schemas import (
    Classificacao,
    DadosComunidade,
    DadosMercado,
    DadosSeguranca,
    ScoreDetalhado,
)


def gerar_parecer(
    mercado: DadosMercado,
    seguranca: DadosSeguranca,
    comunidade: DadosComunidade,
    score: ScoreDetalhado,
    classificacao: Classificacao,
) -> str:
    """Monta um parecer em português, combinando observações relevantes."""
    frases: list[str] = []

    # --- Liquidez ---
    liq = mercado.liquidez_usd or 0
    if liq >= 500_000:
        frases.append("A liquidez é excelente, o que reduz o risco de manipulação de preço.")
    elif liq >= 100_000:
        frases.append("A liquidez está em um nível bom, oferecendo razoável segurança para negociação.")
    elif liq >= 20_000:
        frases.append("A liquidez é moderada, o que pode causar variações bruscas de preço em ordens maiores.")
    else:
        frases.append("A liquidez é baixa, o que representa risco elevado de manipulação e dificuldade para sair da posição.")

    # --- Volume ---
    if score.volume >= 70:
        frases.append("O volume de negociação é saudável e consistente entre as janelas de tempo.")
    elif score.volume >= 40:
        frases.append("O volume apresenta atividade moderada.")
    else:
        frases.append("O volume é baixo ou apresenta padrões irregulares, sinal de atenção.")

    # --- Variação de preço ---
    variacao = mercado.variacao_preco_24h
    if variacao is not None:
        if variacao > 100:
            frases.append(f"Houve um crescimento expressivo de {variacao:.0f}% nas últimas 24 horas, o que aumenta o risco de correção.")
        elif variacao > 20:
            frases.append(f"O token valorizou {variacao:.0f}% nas últimas 24 horas.")
        elif variacao < -30:
            frases.append(f"O token sofreu queda acentuada de {abs(variacao):.0f}% nas últimas 24 horas.")

    # --- Segurança ---
    if not seguranca.dados_disponiveis:
        frases.append("Não foi possível verificar dados de segurança do contrato nesta rede; recomenda-se cautela redobrada.")
    else:
        if seguranca.eh_honeypot is True:
            frases.append("⚠️ O contrato apresenta características de HONEYPOT — é possível comprar, mas pode não ser possível vender. Risco extremo.")
        elif seguranca.eh_honeypot is False:
            frases.append("Não foram identificadas características de honeypot no contrato.")

        if seguranca.contrato_verificado is True:
            frases.append("O contrato é verificado, o que permite auditoria pública do código.")
        elif seguranca.contrato_verificado is False:
            frases.append("O contrato não está verificado publicamente, o que dificulta a auditoria do código.")

        if seguranca.tem_mint_authority is True:
            frases.append("O desenvolvedor mantém autoridade de mint, podendo criar novos tokens e diluir o supply a qualquer momento.")

        if seguranca.tem_freeze_authority is True:
            frases.append("O contrato possui autoridade de freeze, podendo congelar carteiras de holders.")

        if seguranca.top_10_holders_pct is not None:
            if seguranca.top_10_holders_pct >= 70:
                frases.append(f"A concentração é extremamente alta: os 10 maiores holders detêm {seguranca.top_10_holders_pct:.0f}% do supply, risco elevado de venda coordenada.")
            elif seguranca.top_10_holders_pct >= 50:
                frases.append(f"Os 10 maiores holders concentram {seguranca.top_10_holders_pct:.0f}% do supply, o que merece atenção.")
            elif seguranca.top_10_holders_pct <= 20:
                frases.append("A distribuição de holders é saudável, com baixa concentração nos maiores detentores.")

        if seguranca.liquidez_travada_pct is not None:
            if seguranca.liquidez_travada_pct >= 80:
                frases.append("A liquidez está majoritariamente travada, reduzindo o risco de rug pull.")
            elif seguranca.liquidez_travada_pct < 30:
                frases.append("Pouca liquidez está travada, o que aumenta o risco de remoção repentina (rug pull).")

    # --- Comunidade ---
    if comunidade.twitter_seguidores:
        if comunidade.twitter_seguidores >= 50_000:
            frases.append("A comunidade nas redes sociais é robusta, com grande base de seguidores.")
        elif comunidade.twitter_seguidores < 1_000:
            frases.append("A comunidade nas redes sociais ainda é pequena.")
    elif not comunidade.twitter_url:
        frases.append("Não foram encontrados links oficiais de redes sociais, o que dificulta avaliar a comunidade.")

    # --- Idade do token ---
    if mercado.idade_dias is not None:
        if mercado.idade_dias < 1:
            frases.append("O token foi criado há menos de 24 horas — tokens muito novos têm histórico insuficiente para avaliação segura.")
        elif mercado.idade_dias >= 180:
            frases.append("O token já está estabelecido há mais de 6 meses, o que adiciona um histórico positivo de continuidade.")

    return " ".join(frases)


def gerar_recomendacao(classificacao: Classificacao, score: ScoreDetalhado) -> str:
    """Resposta direta às perguntas: vale comprar, esperar, ou só acompanhar?"""

    mapa_recomendacao = {
        Classificacao.MUITO_PROMISSORA: (
            "Os indicadores atuais são favoráveis. Para quem aceita o risco característico de memecoins, "
            "este é um momento razoável para considerar entrada, com gestão de risco adequada (nunca invista mais do que pode perder)."
        ),
        Classificacao.PROMISSORA: (
            "O projeto mostra sinais positivos. Pode valer a pena uma entrada com posição reduzida, "
            "ou aguardar uma possível correção de preço para melhorar o ponto de entrada."
        ),
        Classificacao.VALE_ACOMPANHAR: (
            "Ainda não há indicadores suficientemente fortes para recomendar entrada. "
            "O ideal é acompanhar a evolução de liquidez, volume e segurança antes de decidir."
        ),
        Classificacao.ALTO_RISCO: (
            "Os riscos identificados são significativos. Caso opte por entrar, faça isso apenas com "
            "capital que você está disposto a perder integralmente, e considere posições muito pequenas."
        ),
        Classificacao.NAO_RECOMENDADA: (
            "Os indicadores apontam riscos elevados o suficiente para não recomendar a compra neste momento."
        ),
        Classificacao.POSSIVEL_GOLPE: (
            "⚠️ ATENÇÃO: os indicadores são consistentes com um possível golpe (honeypot ou concentração extrema "
            "combinada com baixa liquidez). Recomendamos fortemente NÃO comprar este token."
        ),
    }

    return mapa_recomendacao.get(classificacao, "Dados insuficientes para gerar uma recomendação segura.")


def determinar_nivel_risco(classificacao: Classificacao) -> str:
    mapa_risco = {
        Classificacao.MUITO_PROMISSORA: "Moderado para o segmento de memecoins",
        Classificacao.PROMISSORA: "Moderado para o segmento de memecoins",
        Classificacao.VALE_ACOMPANHAR: "Médio-alto",
        Classificacao.ALTO_RISCO: "Alto",
        Classificacao.NAO_RECOMENDADA: "Muito alto",
        Classificacao.POSSIVEL_GOLPE: "Extremo — possível perda total",
    }
    return mapa_risco.get(classificacao, "Indeterminado")
