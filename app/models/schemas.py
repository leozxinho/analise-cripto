"""
Schemas Pydantic - estruturas de dados usadas em todo o pipeline de análise.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Rede(str, Enum):
    ETHEREUM = "ethereum"
    SOLANA = "solana"
    BSC = "bsc"
    BASE = "base"
    ARBITRUM = "arbitrum"
    POLYGON = "polygon"
    AVALANCHE = "avalanche"
    SUI = "sui"
    TRON = "tron"
    DESCONHECIDA = "desconhecida"


class Classificacao(str, Enum):
    MUITO_PROMISSORA = "🟢 Muito promissora"
    PROMISSORA = "🟢 Promissora"
    VALE_ACOMPANHAR = "🟡 Vale acompanhar"
    ALTO_RISCO = "🟠 Alto risco"
    NAO_RECOMENDADA = "🔴 Não recomendada"
    POSSIVEL_GOLPE = "⚫ Possível golpe"


class DadosMercado(BaseModel):
    """Dados vindos do DEX Screener."""
    preco_usd: Optional[float] = None
    market_cap: Optional[float] = None
    fdv: Optional[float] = None
    liquidez_usd: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_6h: Optional[float] = None
    volume_1h: Optional[float] = None
    variacao_preco_24h: Optional[float] = None
    compradores_24h: Optional[int] = None
    vendedores_24h: Optional[int] = None
    idade_dias: Optional[float] = None
    num_pools: int = 0
    exchanges: list[str] = Field(default_factory=list)
    pair_address: Optional[str] = None
    rede: Rede = Rede.DESCONHECIDA
    nome: Optional[str] = None
    simbolo: Optional[str] = None
    url_dexscreener: Optional[str] = None
    twitter_url: Optional[str] = None
    telegram_url: Optional[str] = None
    site_oficial: Optional[str] = None


class DadosSeguranca(BaseModel):
    """Dados vindos do GoPlus Security."""
    contrato_verificado: Optional[bool] = None
    eh_honeypot: Optional[bool] = None
    ownership_renunciado: Optional[bool] = None
    tem_mint_authority: Optional[bool] = None
    tem_freeze_authority: Optional[bool] = None
    eh_proxy_contract: Optional[bool] = None
    liquidez_travada_pct: Optional[float] = None
    taxa_compra_pct: Optional[float] = None
    taxa_venda_pct: Optional[float] = None
    top_10_holders_pct: Optional[float] = None
    pct_dev_wallets: Optional[float] = None
    pct_exchange_wallets: Optional[float] = None
    total_holders: Optional[int] = None
    eh_blacklistavel: Optional[bool] = None
    dados_disponiveis: bool = True


class DadosComunidade(BaseModel):
    """Dados de redes sociais / comunidade."""
    twitter_url: Optional[str] = None
    telegram_url: Optional[str] = None
    discord_url: Optional[str] = None
    site_oficial: Optional[str] = None
    twitter_seguidores: Optional[int] = None
    score_comunidade: Optional[float] = None  # 0-100, heurístico


class DisponibilidadeCompra(BaseModel):
    """Onde o token pode ser comprado."""
    wallets_descentralizadas: list[str] = Field(default_factory=list)
    dexs: list[str] = Field(default_factory=list)
    exchanges_centralizadas: list[str] = Field(default_factory=list)


class ScoreDetalhado(BaseModel):
    seguranca: int = 0
    liquidez: int = 0
    comunidade: int = 0
    volume: int = 0
    tokenomics: int = 0
    nota_final: int = 0


class AnaliseCompleta(BaseModel):
    """Resultado final, pronto para formatar e enviar no WhatsApp."""
    query_original: str
    nome: Optional[str] = None
    simbolo: Optional[str] = None
    rede: Rede = Rede.DESCONHECIDA
    contrato: Optional[str] = None

    mercado: DadosMercado
    seguranca: DadosSeguranca
    comunidade: DadosComunidade
    disponibilidade: DisponibilidadeCompra

    score: ScoreDetalhado
    classificacao: Classificacao
    parecer: str
    recomendacao: str
    nivel_risco: str

    erros: list[str] = Field(default_factory=list)
