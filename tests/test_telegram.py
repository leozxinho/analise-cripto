"""Teste rápido de envio via Telegram."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.telegram_service import enviar_mensagem


async def main():
    print("Enviando mensagem de teste no Telegram...")
    ok = await enviar_mensagem("✅ *Memecoin Analyzer funcionando!*\n\nO monitor de tokens Solana está ativo.")
    print("✅ Mensagem enviada com sucesso!" if ok else "❌ Falhou")


asyncio.run(main())
