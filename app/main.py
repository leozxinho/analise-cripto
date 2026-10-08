"""
Aplicação principal - Memecoin Analyzer API

Endpoints:
- GET  /analisar/{query}  -> testa análise manualmente (sem WhatsApp)
- GET  /health            -> healthcheck
- GET  /docs              -> Swagger UI automático

Background:
- loop_monitoramento()    -> varredura automática a cada 5 min
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.logging_config import get_logger, setup_logging
from app.services.monitor_service import loop_monitoramento, loop_heartbeat
from app.services.response_formatter import formatar_resposta_whatsapp
from app.services.token_analyzer import analisar_token

setup_logging()
logger = get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("aplicacao_iniciando", ambiente=settings.app_env)
    monitor_task = asyncio.create_task(loop_monitoramento())
    heartbeat_task = asyncio.create_task(loop_heartbeat())
    yield
    monitor_task.cancel()
    heartbeat_task.cancel()
    for task in (monitor_task, heartbeat_task):
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("aplicacao_encerrando")


app = FastAPI(
    title="Memecoin Analyzer API",
    description=(
        "Monitora automaticamente novos tokens Solana boosted/trending no DEX Screener "
        "e envia análise completa (score, segurança, liquidez) via WhatsApp (CallMeBot). "
        "Score e recomendações são 100% baseados em regras determinísticas, sem uso de IA."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "ok"}


@app.get("/analisar/{query}", response_class=PlainTextResponse, tags=["Análise"])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def analisar_endpoint(request: Request, query: str):
    """
    Testa a análise manualmente sem precisar aguardar a varredura automática.
    Aceita símbolo (ex: PEPE) ou endereço de contrato.
    """
    try:
        analise = await analisar_token(query)
        return formatar_resposta_whatsapp(analise)
    except Exception as e:
        logger.error("erro_endpoint_analisar", erro=str(e), query=query)
        raise HTTPException(status_code=500, detail=f"Erro ao processar análise: {e}")
