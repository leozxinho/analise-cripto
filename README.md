# Memecoin Analyzer 🚀

API REST que analisa memecoins/altcoins automaticamente e envia o resultado pelo WhatsApp.

**100% gratuito** — usa apenas APIs públicas com camada gratuita (DEX Screener, GoPlus Security, CoinGecko) e Evolution API (open-source) para o WhatsApp.

**Sem IA** — todo o score e recomendação são gerados por regras determinísticas, auditáveis e ajustáveis em `app/services/score_engine.py` e `app/services/recommendation_engine.py`.

---

## Como funciona

```
WhatsApp → Evolution API → Webhook (FastAPI) → Token Analyzer
                                                      ↓
                          ┌───────────────┬───────────┴────────────┬──────────────┐
                          ↓               ↓                        ↓              ↓
                    DEX Screener     GoPlus Security          CoinGecko    Trust Wallet List
                    (mercado)        (segurança/honeypot)     (comunidade)  (disponibilidade)
                          ↓               ↓                        ↓              ↓
                          └───────────────┴───────────┬────────────┴──────────────┘
                                                        ↓
                                                  Score Engine
                                              (regras, 0-100, 5 categorias)
                                                        ↓
                                            Recommendation Engine
                                          (parecer + recomendação textual)
                                                        ↓
                                             Response Formatter
                                                        ↓
                                            Evolution API → WhatsApp
```

---

## Pré-requisitos

- Docker e Docker Compose instalados ([guia oficial](https://docs.docker.com/get-docker/))
- Um número de WhatsApp dedicado para o bot (recomendado usar um chip separado do seu pessoal, mas pode usar o mesmo)
- ~10 minutos

---

## Passo a passo de instalação

### 1. Clonar/copiar o projeto

Copie todos os arquivos para uma pasta no seu servidor ou computador.

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` e ajuste pelo menos:

```env
EVOLUTION_API_KEY=escolha-uma-senha-forte-aqui
MEU_WHATSAPP_NUMERO=5514997780712
POSTGRES_PASSWORD=escolha-outra-senha-forte
```

> 💡 `MEU_WHATSAPP_NUMERO` é o número que vai **enviar** as mensagens para o bot analisar (seu número pessoal). O bot só responde para esse número por segurança — você pode remover essa checagem em `app/modules/whatsapp_webhook.py` se quiser que ele responda a qualquer um.

### 3. Subir os containers

```bash
docker compose up -d --build
```

Isso vai subir 4 serviços:
- `api` — a aplicação FastAPI (porta 8000)
- `postgres` — banco de dados
- `redis` — cache
- `evolution-api` — gateway do WhatsApp (porta 8080)

### 4. Conectar o WhatsApp

1. Acesse `http://localhost:8080/manager` (ou `http://SEU_IP:8080/manager` se estiver em VPS)
2. Faça login usando a `EVOLUTION_API_KEY` que você definiu no `.env`
3. Crie uma instância chamada `memecoin-bot` (mesmo nome do `EVOLUTION_INSTANCE_NAME`)
4. Escaneie o QR Code com o WhatsApp que vai rodar o bot (Configurações → Aparelhos conectados → Conectar)
5. Pronto! O WhatsApp está conectado.

### 5. Testar

No WhatsApp configurado como `MEU_WHATSAPP_NUMERO`, envie para o número do bot:

```
PEPE
```

ou

```
0x6982508145454ce325ddbe47a25d4ec3d2311933
```

Em alguns segundos você recebe a análise completa formatada.

---

## Testar sem WhatsApp (via navegador/Swagger)

Enquanto configura o WhatsApp, você pode testar a análise diretamente:

```bash
curl http://localhost:8000/analisar/PEPE
```

Ou abra a documentação interativa: `http://localhost:8000/docs`

---

## Estrutura do projeto

```
app/
├── main.py                          # FastAPI app, rotas, rate limit
├── config.py                        # Configurações (.env)
├── logging_config.py                # Logs estruturados em JSON
├── models/
│   └── schemas.py                   # Modelos Pydantic (contratos de dados)
├── modules/
│   └── whatsapp_webhook.py          # Recebe mensagens do WhatsApp
├── services/
│   ├── dexscreener_service.py       # Fonte: DEX Screener (mercado)
│   ├── goplus_service.py            # Fonte: GoPlus Security (segurança/honeypot)
│   ├── coingecko_service.py         # Fonte: CoinGecko (comunidade)
│   ├── disponibilidade_service.py   # Onde comprar (DEXs + wallets)
│   ├── score_engine.py              # ⭐ Lógica de pontuação (SEM IA)
│   ├── recommendation_engine.py     # ⭐ Parecer e recomendação (SEM IA)
│   ├── token_analyzer.py            # Orquestrador principal
│   ├── response_formatter.py        # Formata texto pro WhatsApp
│   └── whatsapp_service.py          # Envia mensagens (Evolution API)
└── utils/
    ├── http_client.py               # Cliente HTTP com retry automático
    └── cache.py                     # Cache Redis (evita estourar limites grátis)
tests/
└── test_score_engine.py             # Testes unitários da lógica de score
```

---

## APIs utilizadas (todas gratuitas)

| Fonte | O que fornece | Limite gratuito | Precisa de chave? |
|---|---|---|---|
| [DEX Screener](https://docs.dexscreener.com/api/reference) | Liquidez, volume, preço, pools | Generoso, sem limite documentado para uso razoável | Não |
| [GoPlus Security](https://docs.gopluslabs.io) | Honeypot, rug pull, mint/freeze authority, holders | Alto volume gratuito | Não |
| [CoinGecko](https://docs.coingecko.com) | Comunidade, redes sociais | 10-30 req/min sem chave | Não (chave Demo opcional aumenta limite) |
| [Trust Wallet Assets](https://github.com/trustwallet/assets) | Lista pública de tokens suportados | Ilimitado (é um repositório estático) | Não |
| [Evolution API](https://doc.evolution-api.com) | Gateway WhatsApp | Self-hosted, sem limite | Não (é open-source) |

---

## Ajustando o score (sem precisar mexer no resto do código)

Toda a lógica de pontuação está isolada em **`app/services/score_engine.py`**. Os pesos de cada categoria estão centralizados:

```python
PESOS = {
    "seguranca": 0.35,   # 35% da nota final
    "liquidez": 0.25,    # 25%
    "volume": 0.15,      # 15%
    "comunidade": 0.10,  # 10%
    "tokenomics": 0.15,  # 15%
}
```

Os textos do parecer estão em **`app/services/recommendation_engine.py`**, organizados por categoria (liquidez, volume, segurança, comunidade, idade).

---

## Adicionando novas fontes de dados no futuro

A arquitetura foi pensada para isso. Para adicionar uma nova fonte (ex: Birdeye, Helius):

1. Crie `app/services/nova_fonte_service.py` seguindo o padrão dos existentes (uma função async que retorna um schema Pydantic)
2. Adicione os campos relevantes em `app/models/schemas.py` se necessário
3. Chame a nova função em `app/services/token_analyzer.py`, idealmente em paralelo com `asyncio.gather`
4. Ajuste o `score_engine.py` se a nova fonte deve influenciar a pontuação

---

## Rodando os testes

```bash
pip install -r requirements.txt
pip install pytest
pytest tests/ -v
```

---

## Rate Limiting

O endpoint `/analisar/{query}` tem rate limit de 20 requisições/minuto por IP (configurável em `RATE_LIMIT_PER_MINUTE` no `.env`). O webhook do WhatsApp não tem rate limit próprio — ele já é naturalmente limitado pela velocidade de digitação humana, mas você pode adicionar se for expor para muitos usuários.

---

## Limitações conhecidas

- **Binance Alpha / Binance Web3 Wallet**: não possuem API pública, não são verificados automaticamente
- **Coinbase Wallet / Phantom**: verificação de suporte é inferida via DEX (não há API oficial de lista de tokens)
- **Exchanges centralizadas (Binance, OKX, etc)**: o campo `exchanges_centralizadas` fica vazio por padrão, pois confirmar listagem oficial exige fontes adicionais (ex: scraping ou CoinGecko com mapeamento de tickers) — pode ser expandido depois
- **CoinGecko free tier**: sem chave, o limite é baixo (10-30 req/min); o cache Redis (TTL 10 min para comunidade) ajuda a mitigar isso

---

## Próximos passos sugeridos

- [ ] Adicionar Birdeye API para reforçar dados de Solana
- [ ] Adicionar verificação de liquidez travada via Team Finance/Unicrypt (EVM)
- [ ] Persistir histórico de análises no PostgreSQL (tabelas já previstas na arquitetura, banco está rodando mas sem migrations ainda — adicionar com Alembic)
- [ ] Adicionar endpoint de comparação entre tokens
# analise-cripto
