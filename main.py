#!/usr/bin/env python3

"""
🚀 ASYNC MAIN.PY - АСИНХРОННЫЙ БОТ
Использует встроенный event loop telegram-bot-api
"""

import asyncio
import sys
from telegram.ext import Application
from config import TELEGRAM_BOT_TOKEN, DB_AUTO_CLEANUP, DB_CLEANUP_DAYS
from core_llm_service import LLMService
from core_embeddings_service import EmbeddingsService
from core_database_manager import DatabaseManager
from processor_rag_pipeline import RAGPipeline
from telegram_bot_handlers import setup_handlers
from logger import get_logger

logger = get_logger(__name__)

def main():
    """Главная функция запуска бота (СИНХРОННАЯ)"""
    logger.info("✅ Запуск ASYNC RAG Bot...")

    try:
        # ════════════════════════════════════════════════════════════════════
        # ИНИЦИАЛИЗАЦИЯ СЕРВИСОВ
        # ════════════════════════════════════════════════════════════════════

        logger.info("✅ Инициализирую сервисы...")

        # 1. LLM Service
        logger.info("✅ LLMService инициализирована")
        llm = LLMService()

        # 2. Embeddings Service
        logger.info("✅ EmbeddingsService инициализирована")
        embedding = EmbeddingsService()

        # 3. Database Manager
        logger.info("✅ DatabaseManager инициализирована")
        db = DatabaseManager(embeddings_service=embedding)

        # Опционально: очистить старые документы
        if DB_AUTO_CLEANUP:
            logger.info(f"🧹 Очистка документов (старше {DB_CLEANUP_DAYS} дней)...")
            try:
                # Просто выполняем без async, так как это разовая операция при старте
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                deleted = loop.run_until_complete(
                    db.delete_old_documents(days=DB_CLEANUP_DAYS)
                )
                loop.close()
                
                if deleted > 0:
                    logger.info(f"✅ Удалено {deleted} документов")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка очистки: {e}")

        # 4. RAG Pipeline с ASYNC поддержкой
        logger.info("✅ RAG Pipeline инициализирована")
        rag = RAGPipeline(llm, embedding=embedding, db=db)

        # Выведем статистику БД
        db_stats = db.get_stats()
        logger.info(f"✅ БД готова ({db_stats['total_documents']} документов)")

        # ════════════════════════════════════════════════════════════════════
        # ИНИЦИАЛИЗАЦИЯ TELEGRAM БОТА
        # ════════════════════════════════════════════════════════════════════

        logger.info("✅ Telegram Bot инициализирован")
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Добавляем сервисы в bot_data
        app.bot_data['llm'] = llm
        app.bot_data['embedding'] = embedding
        app.bot_data['db'] = db
        app.bot_data['rag'] = rag

        logger.info("✅ Обработчики установлены")

        # Настраиваем обработчики
        setup_handlers(app)

        logger.info("✅ Бот готов к работе!")
        logger.info("💡 Режим: Web-First (поиск в интернете + БД)")
        logger.info(f"📚 Документов в БД: {db_stats['total_documents']}")
        logger.info("═" * 70)

        # (Application сам управляет asyncio event loop внутри)
        app.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )

    except KeyboardInterrupt:
        logger.info("⛔ Бот остановлен (Ctrl+C)")
    except Exception as e:
        logger.error(f"🚨 CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()