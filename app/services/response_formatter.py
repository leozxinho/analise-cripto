"""
Módulo: Response Formatter

Formata a AnaliseCompleta no template visual definido para o WhatsApp.
"""
from app.models.schemas import AnaliseCompleta


def _fmt_money(valor: float | None) -> str:
    if valor is None:
        return "N/D"
    if valor >= 1_000_000_000:
        return f"US$ {valor / 1_000_000_000:.2f}B"
    if valor >= 1_000_000:
        return f"US$ {valor / 1_000_000:.2f}M"
    if valor >= 1_000:
        return f"US$ {valor / 1_000:.2f}K"
    return f"US$ {valor:.2f}"


def _fmt_preco(valor: float | None) -> str:
    if valor is None:
        return "N/D"
    if valor < 0.0001:
        return f"US$ {valor:.10f}".rstrip("0")
    return f"US$ {valor:.6f}".rstrip("0").rstrip(".")


def _fmt_bool(valor: bool | None, invertido: bool = False) -> str:
    """invertido=True quando 'False' é o resultado bom (ex: honeypot=False é bom)."""
    if valor is None:
        return "❓ Não verificado"
    bom = (not valor) if invertido else valor
    emoji = "✅" if bom else "❌"
    texto = "Sim" if valor else "Não"
    return f"{emoji} {texto}"


def formatar_resposta_whatsapp(analise: AnaliseCompleta) -> str:
    if analise.erros and not analise.mercado.simbolo:
        return (
            f"❌ *Não foi possível analisar*\n\n"
            f"{analise.erros[0]}\n\n"
            f"Envie o símbolo (ex: PEPE) ou o endereço do contrato para tentar novamente."
        )

    m = analise.mercado
    s = analise.seguranca
    d = analise.disponibilidade
    sc = analise.score

    linhas = []
    linhas.append("🚀 *Análise Completa*\n")
    linhas.append(f"*Moeda:*\n{m.nome or analise.simbolo or 'N/D'} ({m.simbolo or '?'})\n")
    linhas.append(f"*Rede:*\n{analise.rede.value.title()}\n")
    linhas.append(f"*Preço:*\n{_fmt_preco(m.preco_usd)}\n")
    linhas.append(f"*Market Cap:*\n{_fmt_money(m.market_cap or m.fdv)}\n")
    linhas.append(f"*Liquidez:*\n{_fmt_money(m.liquidez_usd)}\n")
    linhas.append(f"*Volume 24h:*\n{_fmt_money(m.volume_24h)}\n")

    if m.variacao_preco_24h is not None:
        sinal = "+" if m.variacao_preco_24h >= 0 else ""
        linhas.append(f"*Variação 24h:*\n{sinal}{m.variacao_preco_24h:.1f}%\n")

    if s.total_holders is not None:
        linhas.append(f"*Holders:*\n{s.total_holders:,}\n".replace(",", "."))

    if analise.contrato:
        linhas.append(f"*Contrato:*\n`{analise.contrato}`\n")
    if s.contrato_verificado is not None:
        linhas.append(f"*Verificado:*\n{_fmt_bool(s.contrato_verificado)}\n")

    if s.liquidez_travada_pct is not None:
        travada = s.liquidez_travada_pct >= 50
        emoji = "✅" if travada else "⚠️"
        linhas.append(f"*Liquidez Travada:*\n{emoji} {s.liquidez_travada_pct:.0f}%\n")

    if s.eh_honeypot is not None:
        linhas.append(f"*Honeypot:*\n{_fmt_bool(s.eh_honeypot, invertido=True)}\n")
    elif s.dados_disponiveis:
        linhas.append("*Honeypot:*\n⚠️ Não indexado ainda (token muito novo)\n")
    else:
        linhas.append("*Honeypot:*\n❓ Dados indisponíveis nesta rede\n")

    rug_risco = (
        s.eh_honeypot is True
        or (s.top_10_holders_pct or 0) >= 70
        or (s.liquidez_travada_pct is not None and s.liquidez_travada_pct < 20)
    )
    linhas.append(f"*Risco de Rug Pull:*\n{'❌ Identificado' if rug_risco else '✅ Não identificado'}\n")

    linhas.append("\n*Score*\n")
    linhas.append(f"Segurança: {sc.seguranca}")
    linhas.append(f"Liquidez: {sc.liquidez}")
    linhas.append(f"Volume: {sc.volume}")
    linhas.append(f"Comunidade: {sc.comunidade}")
    linhas.append(f"Tokenomics: {sc.tokenomics}\n")

    linhas.append(f"*Nota Geral*\n{sc.nota_final}/100\n")
    linhas.append(f"*Classificação*\n{analise.classificacao.value}\n")

    linhas.append(f"*Análise*\n{analise.parecer}\n")
    linhas.append(f"*Recomendação*\n{analise.recomendacao}\n")

    if d.wallets_descentralizadas or d.dexs:
        linhas.append("*Onde Comprar*")
        for item in d.wallets_descentralizadas:
            linhas.append(f"✅ {item}")
        for item in d.dexs:
            linhas.append(f"✅ {item}")
        linhas.append("")

    linhas.append(f"*Risco*\n{analise.nivel_risco}")

    if analise.erros:
        linhas.append(f"\n_Observação: {'; '.join(analise.erros)}_")

    return "\n".join(linhas)
