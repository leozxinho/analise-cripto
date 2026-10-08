"""
Módulo: WhatsApp Webhook

Recebe eventos da Evolution API quando uma mensagem chega no WhatsApp,
extrai o texto, dispara a análise e responde automaticamente.
"""
from fastapi import APIRouter, BackgroundTasks, Request

from app.config import settings
from app.services.response_formatter import formatar_resposta_whatsapp
from app.services.token_analyzer import analisar_token
from app.services.whatsapp_service import enviar_mensagem_whatsapp
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/webhook/whatsapp")
async def receber_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint chamado pela Evolution API a cada evento.
    Filtramos apenas mensagens de texto recebidas (não enviadas por nós mesmos).
    """
    body = await request.json()

    evento = body.get("event")
    if evento != "messages.upsert":
        return {"status": "ignorado", "motivo": "evento não relevante"}

    dados_mensagem = body.get("data", {})

    # Ignora mensagens enviadas pelo próprio bot (eco)
    if dados_mensagem.get("key", {}).get("fromMe"):
        return {"status": "ignorado", "motivo": "mensagem própria"}

    numero_remetente = _extrair_numero(dados_mensagem)
    texto = _extrair_texto(dados_mensagem)

    if not texto or not numero_remetente:
        return {"status": "ignorado", "motivo": "sem texto ou remetente"}

    # Filtro de segurança: só responde para o número configurado como dono
    # (remova esta checagem se quiser que o bot responda a qualquer pessoa)
    if settings.meu_whatsapp_numero and numero_remetente != settings.meu_whatsapp_numero:
        logger.info("mensagem_ignorada_numero_nao_autorizado", numero=numero_remetente)
        return {"status": "ignorado", "motivo": "número não autorizado"}

    logger.info("mensagem_recebida", numero=numero_remetente, texto=texto)

    # Processa em background para responder rápido ao webhook (evita timeout/retry da Evolution API)
    background_tasks.add_task(processar_e_responder, numero_remetente, texto)

    return {"status": "processando"}


async def processar_e_responder(numero: str, texto: str):
    try:
        analise = await analisar_token(texto)
        resposta = formatar_resposta_whatsapp(analise)
        await enviar_mensagem_whatsapp(numero, resposta)
    except Exception as e:
        logger.error("erro_processamento_mensagem", erro=str(e), numero=numero)
        await enviar_mensagem_whatsapp(
            numero,
            "❌ Ocorreu um erro ao processar sua análise. Tente novamente em instantes.",
        )


def _extrair_numero(dados_mensagem: dict) -> str | None:
    remote_jid = dados_mensagem.get("key", {}).get("remoteJid", "")
    if "@" in remote_jid:
        return remote_jid.split("@")[0]
    return None


def _extrair_texto(dados_mensagem: dict) -> str | None:
    message = dados_mensagem.get("message", {})
    return (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
    )
