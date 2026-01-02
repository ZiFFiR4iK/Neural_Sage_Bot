#!/usr/bin/env python3

"""
RAG Pipeline - обработка запросов с ПАРАЛЛЕЛЬНЫМ поиском (Web + DB)
[FINAL STABLE VERSION]
"""

import asyncio

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
        """Основной метод обработки запроса"""
        if not query or not query.strip():
            return "Пустой запрос. Напиши что-нибудь!"

        mode = user_mode or 'default'
        mode_config = MODE_CONFIGS.get(mode, MODE_CONFIGS['default'])

        logger.info(f"🔄 [{mode.upper()}] Processing: {query[:50]}...")

        # 1. ПАРАЛЛЕЛЬНЫЙ ПОИСК (Web + DB одновременно)
        num_web_results = mode_config.get('web_search_results', 5)

        web_task = asyncio.create_task(self._search_web(query, num_results=num_web_results))
        db_task = asyncio.create_task(self._search_database(query))

        results = await asyncio.gather(web_task, db_task, return_exceptions=True)

        web_results = results[0] if not isinstance(results[0], Exception) else ""
        db_results = results[1] if not isinstance(results[1], Exception) else ""

        if isinstance(results[0], Exception):
            logger.error(f"Web search error: {results[0]}")
        if isinstance(results[1], Exception):
            logger.error(f"DB search error: {results[1]}")

        # 2. ФОРМИРОВАНИЕ КОНТЕКСТА
        final_context = ""

        if web_results:
            final_context += "=== ИНФОРМАЦИЯ ИЗ ИНТЕРНЕТА ===\n\n"
            final_context += web_results + "\n\n"

        if db_results and len(db_results) > 50:
            final_context += "=== ИЗ БАЗЫ ЗНАНИЙ ===\n\n"
            final_context += db_results

        if not final_context:
            logger.warning("No context found from Web or DB")
            return "❌ Я не нашел информации. Попробуй переформулировать."

        # 3. ФОНОВОЕ СОХРАНЕНИЕ
        if web_results:
            asyncio.create_task(self._add_web_results_to_db(web_results, query))

        # 4. ГЕНЕРАЦИЯ ОТВЕТА (просто отправляем, БЕЗ ВАЛИДАЦИИ)
        response = await self._generate_answer(
            query=query,
            context=final_context,
            mode=mode,
            mode_config=mode_config
        )

        return response

    async def _search_database(self, query: str) -> str:
        """Поиск в БД в отдельном потоке"""
        try:
            loop = asyncio.get_event_loop()
            results_text = await loop.run_in_executor(
                None,
                lambda: self.db.search(query, top_k=5)
            )
            return results_text if results_text else ""
        except Exception as e:
            logger.error(f"DB search error: {e}")
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
            logger.error(f"Web search error: {e}")
            return ""

    async def _add_web_results_to_db(self, web_context: str, query: str) -> None:
        """Фоновое сохранение результатов в БД"""
        try:
            parts = web_context.split('\n\n')
            documents = []
            
            for part in parts:
                cleaned = part.strip()
                if len(cleaned) > 50:
                    documents.append({'text': cleaned})

            if documents:
                await self.db.add_documents(documents, source="web_auto")
                logger.info(f"💾 Saved {len(documents)} snippets to DB")
        except Exception as e:
            logger.error(f"Background save error: {e}")

    async def _generate_answer(self, query: str, context: str, mode: str, mode_config: dict) -> str:
        """Генерация ответа через LLM"""
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
            logger.error(f"LLM generation error: {e}")
            return f"❌ Ошибка: {str(e)}"

    def _build_short_prompt(self, query: str, context: str) -> str:
        return f"""Дай краткий ответ (2-3 предложения).
Язык: РУССКИЙ.

Информация:
{context}

Вопрос: {query}

Ответ:"""

    def _build_default_prompt(self, query: str, context: str) -> str:
        return f"""Дай полный ответ на вопрос.
Используй информацию ниже. Структурируй ответ.
Объем: 500-1000 слов.
Язык: РУССКИЙ.

Информация:
{context}

Вопрос: {query}

Ответ:"""

    def _build_detailed_prompt(self, query: str, context: str) -> str:
        return f"""Дай ОЧЕНЬ подробный ответ.
Объясни детали, приведи примеры.
Объем: 1500+ слов.
Язык: РУССКИЙ.

Информация:
{context}

Вопрос: {query}

Ответ:"""
