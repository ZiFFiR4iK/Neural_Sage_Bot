#!/usr/bin/env python3

"""
RAG Pipeline - обработка запросов с поиском в БД и интернете
Логика: БД → (если пусто) → интернет → пополнить БД → ответ
"""

import asyncio
from typing import Optional
from core_llm_service import LLMService
from core_database_manager import DatabaseManager
from core_embeddings_service import EmbeddingsService
from core_web_search_service import WebSearchService
from config import MODE_CONFIGS
from logger import get_logger

logger = get_logger(__name__)


class RAGPipeline:
    def __init__(
        self,
        llm: LLMService,
        embedding: EmbeddingsService,
        db: DatabaseManager,
    ):
        self.llm = llm
        self.embedding = embedding
        self.db = db
        self.web_search = WebSearchService()

    async def process(self, query: str, user_mode: str = None) -> str:
        """
        🎯 ФИНАЛЬНАЯ ВЕРСИЯ ЛОГИКИ:
        1. Поиск в БД (всегда)
        2. Если в БД достаточно информации (>1200 символов) -> используем БД, пропускаем веб.
        3. Если мало -> ищем в вебе -> добавляем в БД -> используем всё вместе.
        """
        
        if not query or not query.strip():
            return "Пустой запрос. Напиши что-нибудь!"
        
        mode = user_mode or 'default'
        mode_config = MODE_CONFIGS.get(mode, MODE_CONFIGS['default'])
        
        logger.info(f"🔄 [{mode.upper()}] Обработка: {query[:50]}...")
        
        # 1. Поиск в БД
        db_context = ""
        # ВАЖНО: top_k побольше, чтобы набрать объем
        db_results = await self._search_database(query, mode=mode)
        
        # Считаем реальный объем полезной информации
        db_content_len = len(db_results) if db_results else 0
        
        # Логика решения о веб-поиске
        need_web_search = True
        
        if db_content_len > 1200:  # Если нашли > 1200 символов качественного текста
            logger.info(f"✅ БД достаточно ({db_content_len} chars), веб-поиск пропущен")
            db_context = db_results
            need_web_search = False
        elif db_content_len > 0:
            logger.info(f"⚠️ БД частично полна ({db_content_len} chars), нужен веб-поиск...")
            db_context = db_results
        else:
            logger.info(f"❌ БД пуста")
        
        # 2. Веб-поиск (только если нужно)
        if need_web_search:
            num_web_results = mode_config.get('web_search_results', 5)
            logger.info(f"🌐 Web поиск ({num_web_results} результатов)...")
            
            web_results = await self._search_web(query, num_results=num_web_results)
            
            if web_results:
                # Если в БД уже что-то было, добавляем веб-результаты к контексту
                if db_context:
                    db_context += "\n\n=== ДОПОЛНИТЕЛЬНО ИЗ ИНТЕРНЕТА ===\n\n" + web_results
                else:
                    db_context = web_results
                
                # Асинхронно сохраняем в БД
                await self._add_web_results_to_db(web_results, query)
                logger.info(f"✅ Web результаты добавлены в БД")
            else:
                logger.warning(f"⚠️ Web поиск не вернул результаты")
        
        # 3. Если вообще ничего нет
        if not db_context:
            return "❌ Я не нашел информации ни в базе знаний, ни в интернете. Попробуй переформулировать запрос."
        
        # 4. Генерация
        response = await self._generate_answer(
            query=query,
            context=db_context,
            mode=mode,
            mode_config=mode_config
        )
        
        return response

    async def _search_database(self, query: str, mode: str = 'default') -> str:
        """Поиск в БД с ограничением по режиму (возвращает строку контекста)"""
        try:
            loop = asyncio.get_event_loop()
            
            # search() теперь возвращает уже готовый текст (str), не список
            results_text = await loop.run_in_executor(
                None,
                lambda: self.db.search(query, top_k=10)
            )
            
            # Результат уже отформатирован в search(), просто возвращаем
            if results_text and len(results_text.strip()) > 0:
                return results_text
            else:
                return ""
        
        except Exception as e:
            logger.error(f"❌ Ошибка поиска БД: {e}")
            return ""

    async def _search_web(self, query: str, num_results: int = 5) -> str:
        """Поиск в интернете"""
        try:
            results = await self.web_search.search(query, num_results=num_results)

            if not results:
                return ""

            context = ""
            for i, result in enumerate(results, 1):
                title = result.get('title', '').strip()
                snippet = result.get('snippet', '').strip()
                url = result.get('url', '')

                if title and snippet:
                    context += f"{i}. {title}\n{snippet}\n"
                
                if url:
                    context += f"Источник: {url}\n"
                
                context += "\n"

            return context.strip()

        except Exception as e:
            logger.error(f"❌ Ошибка web поиска: {e}")
            return ""

    async def _add_web_results_to_db(self, web_context: str, query: str) -> None:
        """Асинхронно добавить результаты веб-поиска в БД"""
        try:
            logger.info(f"📥 Добавляю web результаты в БД...")
            parts = web_context.split('\n\n')
            documents = [{'text': part.strip()} for part in parts if part.strip() and len(part.strip()) > 20]
            
            if documents:
                # Теперь используем await вместо run_in_executor
                await self.db.add_documents(documents, source="web_auto")
                logger.info(f"✅ Добавлено {len(documents)} документов")
        
        except Exception as e:
            logger.error(f"❌ Ошибка добавления в БД: {e}")

    async def _generate_answer(
        self,
        query: str,
        context: str,
        mode: str,
        mode_config: dict
    ) -> str:
        """Генерировать ответ с учётом режима"""
        try:
            if mode == 'short':
                prompt = self._build_short_prompt(query, context)
            elif mode == 'default':
                prompt = self._build_default_prompt(query, context)
            else:
                prompt = self._build_detailed_prompt(query, context)

            response = self.llm.generate(
                prompt=prompt,
                context=context,
                mode=mode
            )

            return response

        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")
            return f"❌ Ошибка при генерации ответа: {str(e)}"

    def _build_short_prompt(self, query: str, context: str) -> str:
        """Промпт для SHORT режима (компактный ответ)"""
        if not context:
            return f"""Ты помощник. Дай краткий, прямой ответ в 2-3 предложениях.
    Язык: РУССКИЙ

    Вопрос: {query}

    Ответ (кратко, 2-3 предложения):"""
        
        return f"""Дай краткий, прямой ответ на основе информации ниже.
    Ответ должен быть ровно 2-3 предложениями, выделяй самое важное.
    Язык: РУССКИЙ

    Информация:
    {context}

    Вопрос: {query}

    Ответ (кратко, 2-3 предложения):"""

    def _build_default_prompt(self, query: str, context: str) -> str:
        """Промпт для DEFAULT режима (нормальный ответ)"""
        if not context:
            return f"""Ты помощник. Дай полный и понятный ответ.
    Объем: 800-1000 слов.
    Язык: РУССКИЙ

    Вопрос: {query}

    Ответ (полный, с примерами):"""
        
        return f"""Дай полный и понятный ответ на вопрос.
    Используй информацию ниже, добавляй примеры если они помогают.
    Структурируй ответ, используй списки и подзаголовки где необходимо.
    Объем: 800-1000 слов.
    Язык: РУССКИЙ

    Информация:
    {context}

    Вопрос: {query}

    Ответ (полный, с примерами и структурой):"""

    def _build_detailed_prompt(self, query: str, context: str) -> str:
        """Промпт для DETAILED режима (подробный ответ)"""
        if not context:
            return f"""Ты эксперт. Дай ОЧЕНЬ подробный и развёрнутый ответ.
    Объем: 1500-2500 слов.
    Язык: РУССКИЙ

    Вопрос: {query}

    Подробный ответ (со всеми деталями, примерами, кодом):"""
        
        return f"""Дай ОЧЕНЬ подробный и развёрнутый ответ на вопрос.
    Объясни каждый аспект, добавь примеры кода если это помогает.
    Покрой все стороны темы, будь творческим в подходе.
    Используй таблицы, списки, подзаголовки для структурирования.
    Ответ должен быть информативным, полезным и полным.
    Объем: 1500-2500 слов.
    Язык: РУССКИЙ

    Информация:
    {context}

    Вопрос: {query}

    Подробный ответ (со всеми деталями, примерами, таблицами, кодом):"""