"""
Testes unitários do Score Engine — a parte mais crítica do sistema
(é o que decide se um token parece seguro ou não).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.schemas import DadosComunidade, DadosMercado, DadosSeguranca, Rede, Classificacao
from app.services.score_engine import (
    calcular_score_geral,
    calcular_score_liquidez,
    calcular_score_seguranca,
    classificar,
)


def test_liquidez_excelente_pontua_alto():
    mercado = DadosMercado(liquidez_usd=1_000_000)
    assert calcular_score_liquidez(mercado) >= 90


def test_liquidez_zero_pontua_zero():
    mercado = DadosMercado(liquidez_usd=0)
    assert calcular_score_liquidez(mercado) == 0


def test_liquidez_baixa_pontua_baixo():
    mercado = DadosMercado(liquidez_usd=5_000)
    assert calcular_score_liquidez(mercado) < 30


def test_honeypot_zera_score_seguranca():
    seguranca = DadosSeguranca(eh_honeypot=True, dados_disponiveis=True)
    assert calcular_score_seguranca(seguranca) == 0


def test_contrato_seguro_pontua_alto():
    seguranca = DadosSeguranca(
        eh_honeypot=False,
        contrato_verificado=True,
        ownership_renunciado=True,
        tem_mint_authority=False,
        liquidez_travada_pct=90,
        top_10_holders_pct=15,
        dados_disponiveis=True,
    )
    assert calcular_score_seguranca(seguranca) >= 80


def test_dados_indisponiveis_retorna_score_neutro():
    seguranca = DadosSeguranca(dados_disponiveis=False)
    score = calcular_score_seguranca(seguranca)
    assert 0 < score < 60  # neutro-baixo, nunca alto


def test_honeypot_classifica_como_possivel_golpe():
    mercado = DadosMercado(liquidez_usd=100_000)
    seguranca = DadosSeguranca(eh_honeypot=True, dados_disponiveis=True)
    comunidade = DadosComunidade()
    score = calcular_score_geral(mercado, seguranca, comunidade)
    classificacao = classificar(score, seguranca, mercado)
    assert classificacao == Classificacao.POSSIVEL_GOLPE


def test_concentracao_extrema_com_baixa_liquidez_e_golpe():
    mercado = DadosMercado(liquidez_usd=5_000)
    seguranca = DadosSeguranca(
        eh_honeypot=False, top_10_holders_pct=85, dados_disponiveis=True
    )
    comunidade = DadosComunidade()
    score = calcular_score_geral(mercado, seguranca, comunidade)
    classificacao = classificar(score, seguranca, mercado)
    assert classificacao == Classificacao.POSSIVEL_GOLPE


def test_token_solido_classifica_promissor():
    mercado = DadosMercado(
        liquidez_usd=800_000,
        volume_24h=500_000,
        market_cap=5_000_000,
        volume_1h=20_000,
        compradores_24h=100,
        vendedores_24h=80,
        idade_dias=200,
        num_pools=3,
    )
    seguranca = DadosSeguranca(
        eh_honeypot=False,
        contrato_verificado=True,
        ownership_renunciado=True,
        tem_mint_authority=False,
        liquidez_travada_pct=90,
        top_10_holders_pct=15,
        total_holders=15000,
        dados_disponiveis=True,
    )
    comunidade = DadosComunidade(score_comunidade=80)
    score = calcular_score_geral(mercado, seguranca, comunidade)
    classificacao = classificar(score, seguranca, mercado)
    assert classificacao in (Classificacao.MUITO_PROMISSORA, Classificacao.PROMISSORA)
    assert score.nota_final >= 70


def test_score_geral_nunca_excede_100():
    mercado = DadosMercado(liquidez_usd=10_000_000, volume_24h=10_000_000, idade_dias=1000, num_pools=10)
    seguranca = DadosSeguranca(
        eh_honeypot=False, contrato_verificado=True, ownership_renunciado=True,
        tem_mint_authority=False, liquidez_travada_pct=100, top_10_holders_pct=5,
        total_holders=1_000_000, dados_disponiveis=True,
    )
    comunidade = DadosComunidade(score_comunidade=100)
    score = calcular_score_geral(mercado, seguranca, comunidade)
    assert score.nota_final <= 100


def test_score_geral_nunca_negativo():
    mercado = DadosMercado(liquidez_usd=0)
    seguranca = DadosSeguranca(
        eh_honeypot=False, contrato_verificado=False, tem_mint_authority=True,
        tem_freeze_authority=True, eh_proxy_contract=True, eh_blacklistavel=True,
        liquidez_travada_pct=0, taxa_compra_pct=50, taxa_venda_pct=50,
        top_10_holders_pct=99, dados_disponiveis=True,
    )
    comunidade = DadosComunidade()
    score = calcular_score_geral(mercado, seguranca, comunidade)
    assert score.nota_final >= 0


if __name__ == "__main__":
    import traceback

    testes = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passou, falhou = 0, 0
    for teste in testes:
        try:
            teste()
            print(f"✅ {teste.__name__}")
            passou += 1
        except AssertionError:
            print(f"❌ {teste.__name__}")
            traceback.print_exc()
            falhou += 1
    print(f"\n{passou} passaram, {falhou} falharam de {len(testes)} testes")
