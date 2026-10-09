"""
Cliente HTTP base com retry automático e timeout.
Usado por todos os serviços que consultam APIs externas.
"""
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.logging_config import get_logger

logger = get_logger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class APIClientError(Exception):
    """Erro genérico ao consultar uma API externa."""
    def __init__(self, fonte: str, mensagem: str):
        self.fonte = fonte
        self.mensagem = mensagem
        super().__init__(f"[{fonte}] {mensagem}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=8),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)
async def get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    fonte: str = "desconhecida",
) -> dict | list | None:
    """
    Faz GET e retorna JSON. Retenta automaticamente em timeout/erro de conexão.
    Retorna None silenciosamente em 404 (token não encontrado é um caso normal).
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 404:
                logger.info("recurso_nao_encontrado", fonte=fonte, url=url)
                return None

            if response.status_code == 429:
                logger.warning("rate_limit_atingido", fonte=fonte, url=url)
                raise APIClientError(fonte, "Rate limit atingido, tente novamente em instantes")

            response.raise_for_status()
            return response.json()

    except APIClientError:
        raise  # já tratado acima, não re-logar
    except httpx.HTTPStatusError as e:
        logger.error("erro_http", fonte=fonte, status=e.response.status_code, url=url)
        raise APIClientError(fonte, f"HTTP {e.response.status_code}") from e
    except httpx.TimeoutException:
        logger.error("timeout", fonte=fonte, url=url)
        raise
    except Exception as e:
        logger.error("erro_inesperado", fonte=fonte, erro=str(e), url=url)
        raise APIClientError(fonte, str(e)) from e
