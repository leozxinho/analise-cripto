# Memecoin Analyzer

Monitor automático de novos tokens Solana. A cada 5 minutos busca tokens boosted/trending no DEX Screener, analisa os que foram listados nos últimos 15 minutos e envia um alerta no **Telegram** quando encontra algo que passa nos filtros de qualidade.

**100% gratuito** — DEX Screener, GoPlus Security e CoinGecko (APIs públicas) + Telegram Bot API.

**Sem IA** — score e recomendações gerados por regras determinísticas, auditáveis em `app/services/score_engine.py`.

---

## Como funciona

```
A cada 5 minutos:
  DEX Screener (boosted tokens)
         ↓
  Filtra: Solana + listado há menos de 15 min
         ↓
  Para cada token novo:
    ┌────────────┬──────────────┬────────────────┐
    ↓            ↓              ↓                ↓
DEX Screener  GoPlus        CoinGecko      Trust Wallet
 (mercado)   (segurança)   (comunidade)  (disponibilidade)
    └────────────┴──────────────┴────────────────┘
                          ↓
                    Score Engine
                 (0-100, 5 categorias)
                          ↓
              Filtros: score ≥ 35, liquidez ≥ $5k,
                       não é golpe/não recomendado
                          ↓
               Notificação no Telegram
```

---

## Configuração rápida

### 1. Criar o bot do Telegram

1. Abra o Telegram e mande `/newbot` para **@BotFather**
2. Escolha um nome e username para o bot
3. Guarde o **token** gerado (ex: `1234567890:AAF...`)
4. Mande qualquer mensagem para o seu novo bot para ativá-lo
5. Descubra seu **chat_id** mandando `/start` para **@userinfobot**

### 2. Configurar o `.env`

```bash
cp .env.example .env
```

Edite o `.env`:

```env
TELEGRAM_BOT_TOKEN = seu-token-aqui
TELEGRAM_CHAT_ID   = seu-chat-id-aqui
```

As demais variáveis já têm valores padrão funcionais.

### 3. Rodar localmente

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Ou com Docker:

```bash
docker compose up -d --build
```

Ao iniciar, o app envia uma mensagem de confirmação no Telegram e começa a monitorar.

---

## Deploy no Railway (gratuito)

1. Suba o projeto no GitHub
2. Acesse [railway.app](https://railway.app) → **New Project → Deploy from GitHub**
3. Selecione o repositório
4. Em **Variables**, confirme que `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` estão definidos
5. Railway detecta o `Dockerfile` e faz o deploy automaticamente

> O `.env` já é copiado para o container durante o build, então as variáveis são lidas diretamente dele.

---

## Filtros de qualidade

Tokens são descartados silenciosamente se:

| Critério | Valor |
|---|---|
| Idade | Mais de 15 minutos desde a listagem |
| Classificação | Possível golpe ou Não recomendada |
| Score mínimo | Abaixo de 35/100 |
| Liquidez mínima | Abaixo de US$ 5.000 |

Tokens que passam em todos os critérios geram uma notificação no Telegram.

---

## Sistema de score (0–100)

Calculado sem IA, 100% por regras em `app/services/score_engine.py`:

| Categoria | Peso | O que avalia |
|---|---|---|
| Segurança | 35% | Honeypot, contrato verificado, mint/freeze authority, holders concentrados |
| Liquidez | 25% | Valor em USD disponível nos pools |
| Volume | 15% | Volume 24h vs market cap, consistência entre janelas |
| Tokenomics | 15% | Idade do token, número de holders |
| Comunidade | 10% | Seguidores no Twitter, presença no Telegram/site |

**Classificações:**

| Score | Classificação |
|---|---|
| ≥ 85 | 🟢 Muito promissora |
| ≥ 70 | 🟢 Promissora |
| ≥ 50 | 🟡 Vale acompanhar |
| ≥ 30 | 🟠 Alto risco |
| < 30 | 🔴 Não recomendada |
| Honeypot ou concentração extrema | ⚫ Possível golpe |

---

## Estrutura do projeto

```
app/
├── main.py                        # FastAPI app + background tasks
├── config.py                      # Configurações (.env)
├── logging_config.py              # Logs estruturados
├── models/
│   └── schemas.py                 # Modelos Pydantic
├── services/
│   ├── monitor_service.py         # Loop de monitoramento (5 min)
│   ├── telegram_service.py        # Envia notificações
│   ├── token_analyzer.py          # Orquestrador principal
│   ├── dexscreener_service.py     # Mercado (preço, liquidez, volume)
│   ├── goplus_service.py          # Segurança (honeypot, rug pull)
│   ├── coingecko_service.py       # Comunidade (redes sociais)
│   ├── disponibilidade_service.py # Onde comprar (DEXs + wallets)
│   ├── score_engine.py            # Lógica de pontuação
│   ├── recommendation_engine.py   # Parecer e recomendação textual
│   └── response_formatter.py      # Formata a mensagem final
└── utils/
    ├── http_client.py             # HTTP com retry automático
    └── cache.py                   # Cache em memória com TTL
tests/
├── test_score_engine.py           # Testes unitários do score
└── test_telegram.py               # Teste de envio no Telegram
```

---

## Testando manualmente

Analisa um token pelo símbolo ou endereço de contrato sem esperar a varredura automática:

```bash
curl http://localhost:8000/analisar/PEPE
```

Documentação interativa: `http://localhost:8000/docs`

---

## Rodando os testes

```bash
pip install pytest
pytest tests/test_score_engine.py -v
```

---

## APIs utilizadas (todas gratuitas)

| Fonte | O que fornece | Precisa de chave? |
|---|---|---|
| [DEX Screener](https://docs.dexscreener.com/api/reference) | Liquidez, volume, preço, boosted tokens | Não |
| [GoPlus Security](https://docs.gopluslabs.io) | Honeypot, rug pull, holders, taxas | Não |
| [CoinGecko](https://docs.coingecko.com) | Comunidade, redes sociais | Não (chave Demo opcional) |
| [Trust Wallet Assets](https://github.com/trustwallet/assets) | Lista de tokens suportados | Não |
| [Telegram Bot API](https://core.telegram.org/bots/api) | Envio de notificações | Sim (gratuito via @BotFather) |

---

## Ajustando os filtros

Todos os filtros e pesos ficam em dois arquivos:

- **`app/services/monitor_service.py`** — `MIN_SCORE`, `MIN_LIQUIDEZ_USD`, `MAX_TOKEN_AGE_MINUTES`
- **`app/services/score_engine.py`** — pesos das categorias (`PESOS`)
