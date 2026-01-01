#!/usr/bin/env python3

"""
HANDLERS - Обработчики Telegram команд и сообщений
"""

import asyncio
import traceback
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.constants import ChatAction
from telegram_bot_message_formatter import format_response, clean_response_for_telegram
from telegram_bot_keyboards import get_persistent_keyboard
from logger import get_logger

logger = get_logger(__name__)

TELEGRAM_MAX_MESSAGE_LENGTH = 4096

HELP_TEXT = """🤖 RAG Bot - Справка

Я помогаю находить информацию в интернете и базе данных, потом отвечаю используя AI.

РЕЖИМЫ РАБОТЫ:

🟢 Кратко (300-500 слов)
Быстрые, краткие ответы. Идеально для быстрых вопросов.

🟡 Нормально (800-1000 слов)
Полные ответы с примерами. Стандартный режим.

🔴 Подробно (1500-2500 слов)
Очень подробные ответы со всеми деталями и примерами.

КАК ИСПОЛЬЗОВАТЬ:

1. Выбери режим кнопкой внизу (Кратко/Нормально/Подробно)
2. Напиши вопрос
3. Получи ответ в выбранном режиме

КОМАНДЫ:

/start - начать заново
/help - эта справка
"""


async def send_long_message(message, text: str, reply_markup=None):
    """
    Отправляет длинное сообщение по частям.
    ТОЛЬКО plain text - БЕЗ parse_mode.
    Это гарантирует что сообщение дойдет.
    """
    if not text or len(text.strip()) == 0:
        return
    
    chunk_size = 4096
    
    for i in range(0, len(text), chunk_size):
        part = text[i:i + chunk_size]
        try:
            # БЕЗ parse_mode - только plain text!
            await message.reply_text(
                part,
                reply_markup=reply_markup if i == 0 else None
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")


async def send_typing_status(update, interval: float = 5.0):
    """
    Отправляет статус "печатает" каждые `interval` секунд.
    Используется в фоне для долгих операций.
    """
    try:
        while True:
            await update.message.chat.send_action(ChatAction.TYPING)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"❌ Ошибка typing status: {e}")


async def start(update, context):
    """Команда /start"""
    try:
        context.user_data['mode'] = 'default'
        welcome_msg = """🤖 Добро пожаловать в RAG Bot!

Выбери режим внизу экрана и напиши вопрос. Я буду искать информацию и отвечать.

📚 Справка - для информации о режимах работы."""
        
        await update.message.reply_text(
            welcome_msg,
            reply_markup=get_persistent_keyboard()
        )
        
        logger.info(f"✅ Пользователь {update.effective_user.id} запустил /start")
    except Exception as e:
        logger.error(f"❌ Ошибка /start: {e}")
        try:
            await update.message.reply_text("Ошибка при инициализации")
        except:
            pass


async def help_command(update, context):
    """Команда /help или кнопка Справка"""
    try:
        await update.message.reply_text(
            HELP_TEXT,
            reply_markup=get_persistent_keyboard()
        )
        logger.info(f"ℹ️ Справка отправлена пользователю {update.effective_user.id}")
    except Exception as e:
        logger.error(f"❌ Ошибка /help: {e}")


async def handle_message(update, context):
    """Обработчик всех текстовых сообщений"""
    query = update.message.text
    
    try:
        # ========== СПРАВКА ==========
        if query == "📚 Справка":
            await help_command(update, context)
            return

        # ========== СМЕНА РЕЖИМА ==========
        if query == "🟢 Кратко":
            context.user_data['mode'] = 'short'
            await update.message.reply_text(
                "🟢 Режим Кратко активирован.\n\nТеперь ты получишь ответы 300-500 слов.",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"✅ Режим SHORT включен для {update.effective_user.id}")
            return

        if query == "🟡 Нормально":
            context.user_data['mode'] = 'default'
            await update.message.reply_text(
                "🟡 Режим Нормально активирован.\n\nТеперь ты получишь ответы 800-1000 слов.",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"✅ Режим DEFAULT включен для {update.effective_user.id}")
            return

        if query == "🔴 Подробно":
            context.user_data['mode'] = 'detailed'
            await update.message.reply_text(
                "🔴 Режим Подробно активирован.\n\nТеперь ты получишь ответы 1500-2500 слов с полными деталями.",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"✅ Режим DETAILED включен для {update.effective_user.id}")
            return

        # ========== ОБРАБОТКА ВОПРОСА ==========
        if not query or not query.strip():
            await update.message.reply_text(
                "Пустой запрос. Напиши вопрос!",
                reply_markup=get_persistent_keyboard()
            )
            return

        logger.info(f"📨 Запрос от {update.effective_user.id}: {query[:40]}...")

        current_mode = context.user_data.get('mode', 'default')
        
        # ========== СТАРТУЕМ ФОНОВЫЙ СТАТУС "ПЕЧАТАЕТ" ==========
        typing_task = asyncio.create_task(send_typing_status(update, interval=4.5))
        
        rag = context.application.bot_data.get('rag')
        if not rag:
            typing_task.cancel()
            await update.message.reply_text(
                "❌ RAG модуль не инициализирован",
                reply_markup=get_persistent_keyboard()
            )
            logger.error("❌ RAG Pipeline не инициализирована")
            return

        # Получаем ответ (долгая операция)
        response = await rag.process(query, current_mode)
        
        # ========== ОСТАНАВЛИВАЕМ ФОНОВЫЙ СТАТУС ==========
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass
        
        # Форматируем
        formatted_response = format_response(response)
        cleaned_response = clean_response_for_telegram(formatted_response)

        # Отправляем безопасно - БЕЗ parse_mode
        await send_long_message(
            update.message,
            cleaned_response,
            reply_markup=get_persistent_keyboard()
        )

        logger.info(f"✅ Ответ отправлен пользователю {update.effective_user.id}")

    except Exception as e:
        logger.error(f"❌ Ошибка обработки сообщения: {e}")
        try:
            await update.message.reply_text(
                "❌ Ошибка при обработке запроса",
                reply_markup=get_persistent_keyboard()
            )
        except:
            pass


def setup_handlers(app: Application):
    """Устанавливает обработчики"""
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))