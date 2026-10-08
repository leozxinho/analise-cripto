"""Teste rápido de envio via CallMeBot."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.callmebot_service import enviar_mensagem_whatsapp
from app.config import settings


async def main():
    print(f"Enviando mensagem para {settings.meu_whatsapp_numero}...")
    ok = await enviar_mensagem_whatsapp(
        settings.meu_whatsapp_numero,
        "✅ Memecoin Analyzer funcionando! O monitor de tokens Solana está ativo.",
    )
    print("✅ Mensagem enviada com sucesso!" if ok else "❌ Falhou — verifique CALLMEBOT_API_KEY e MEU_WHATSAPP_NUMERO no .env")


asyncio.run(main())
