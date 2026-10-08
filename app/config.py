"""
Configurações centrais da aplicação.
Carrega variáveis de ambiente do .env
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # WhatsApp (CallMeBot)
    callmebot_api_key: str = ""
    meu_whatsapp_numero: str = ""

    # Cache
    redis_url: str = "redis://redis:6379/0"
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
