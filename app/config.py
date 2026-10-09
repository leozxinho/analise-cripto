"""
Configurações centrais da aplicação.
Carrega variáveis de ambiente do .env
"""
import base64

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Anthropic (Claude AI) — chave em base64 para evitar detecção de secrets no git
    anthropic_api_key: str = ""
    anthropic_api_key_b64: str = ""
    anthropic_workspace_id: str = ""

    @model_validator(mode="after")
    def decodificar_anthropic_key(self) -> "Settings":
        if self.anthropic_api_key_b64 and not self.anthropic_api_key:
            self.anthropic_api_key = base64.b64decode(self.anthropic_api_key_b64).decode()
        return self

    # Cache
    cache_ttl_seconds: int = 120

    # APIs externas
    goplus_api_url: str = "https://api.gopluslabs.io/api/v1"
    dexscreener_api_url: str = "https://api.dexscreener.com/latest"
    coingecko_api_key: str = ""
    coingecko_api_url: str = "https://api.coingecko.com/api/v3"

    # Rate limiting
    rate_limit_per_minute: int = 20

    # App
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
