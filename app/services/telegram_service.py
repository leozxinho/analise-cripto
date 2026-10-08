"""
Módulo: Telegram Sender

Envia mensagens via Telegram Bot API — gratuito, sem limites, sem pausas.
Docs: https://core.telegram.org/bots/api#sendmessage
"""
import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def enviar_mensagem(texto: str) -> bool:
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": texto,
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("telegram_enviado", chat_id=settings.telegram_chat_id)
            return True
    except httpx.HTTPStatusError as e:
        logger.error("telegram_falhou", status=e.response.status_code, resposta=e.response.text)
        return False
    except Exception as e:
        logger.error("telegram_falhou", erro=str(e))
        return False
