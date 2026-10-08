"""
Módulo: WhatsApp Sender (Evolution API)

Evolution API é open-source e gratuita. Docs: https://doc.evolution-api.com
"""
import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def enviar_mensagem_whatsapp(numero: str, texto: str) -> bool:
    """
    Envia mensagem de texto via Evolution API.
    numero: formato internacional sem símbolos, ex: 5514997780712
    """
    url = f"{settings.evolution_api_url}/message/sendText/{settings.evolution_instance_name}"

    payload = {
        "number": numero,
        "text": texto,
    }

    headers = {
        "apikey": settings.evolution_api_key,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info("whatsapp_enviado", numero=numero)
            return True
    except httpx.HTTPStatusError as e:
        logger.error(
            "falha_envio_whatsapp",
            numero=numero,
            status=e.response.status_code,
            resposta=e.response.text,
        )
        return False
    except Exception as e:
        logger.error("falha_envio_whatsapp", numero=numero, erro=str(e))
        return False
