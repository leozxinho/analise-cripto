"""
Módulo: WhatsApp Sender (CallMeBot)

Serviço gratuito que envia mensagens via WhatsApp sem necessidade de
hospedar um gateway próprio. Requer apenas apikey pessoal.
Docs: https://www.callmebot.com/blog/free-api-whatsapp-messages/
"""
import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"


async def enviar_mensagem_whatsapp(numero: str, texto: str) -> bool:
    """
    Envia mensagem via CallMeBot.
    numero: formato internacional sem + ou espaços, ex: 5514997780712
    """
    params = {
        "phone": numero,
        "text": texto,
        "apikey": settings.callmebot_api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(CALLMEBOT_URL, params=params)
            response.raise_for_status()
            logger.info("callmebot_enviado", numero=numero)
            return True
    except httpx.HTTPStatusError as e:
        logger.error(
            "callmebot_falhou",
            numero=numero,
            status=e.response.status_code,
            resposta=e.response.text,
        )
        return False
    except Exception as e:
        logger.error("callmebot_falhou", numero=numero, erro=str(e))
        return False
