#!/usr/bin/env python3
"""
📚 DATABASE MANAGER - Управление Chroma БД с embeddings
"""

import chromadb
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import asyncio
from config import (
    CHROMA_PATH,
    CHROMA_COLLECTION_NAME,
    CHROMA_SIMILARITY_THRESHOLD,
    EMBEDDING_MODEL,
)
from logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Менеджер для работы с Chroma БД"""

    def __init__(self, embeddings_service=None):
        """Инициализация БД"""
        logger.info(f"✅ DatabaseManager инициализирована (path={CHROMA_PATH})")
        
        try:
            # Создаём директорию если её нет
            Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
            
            self.client = chromadb.PersistentClient(path=CHROMA_PATH)
            
            # Получаем или создаём коллекцию
            self.collection = self.client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            
            self.embeddings_service = embeddings_service
            logger.info(f"✅ Коллекция создана: {CHROMA_COLLECTION_NAME}")
            
            stats = self.get_stats()
            logger.info(f"✅ БД готова ({stats['total_documents']} документов)")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
            raise

    def __init__(self, embeddings_service=None):
        """Инициализация БД"""
        logger.info(f"📚 Инициализирую DatabaseManager (path={CHROMA_PATH})...")
        
        try:
            # Создаём директорию если её нет
            Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)

            self.client = chromadb.PersistentClient(path=CHROMA_PATH)

            # Получаем или создаём коллекцию
            self.collection = self.client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )

            self.embeddings_service = embeddings_service
            
            self.write_lock = asyncio.Lock()
            
            logger.info(f"✅ БД инициализирована: {CHROMA_COLLECTION_NAME}")
            stats = self.get_stats()
            logger.info(f"📊 БД статистика: {stats['total_documents']} документов")
        
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
            raise

    async def add_documents(self, documents: list, source: str = "manual") -> bool:
        """Добавить документы в БД (с блокировкой для одновременных запросов)"""
        if not documents:
            return False
        
        # Блокируем запись если идет другая операция записи
        async with self.write_lock:
            try:
                # Убедимся что documents это список dict с 'text'
                processed_docs = []
                for doc in documents:
                    if isinstance(doc, dict):
                        text = doc.get('text', str(doc))
                    else:
                        text = str(doc)
                    
                    if text and len(text.strip()) > 10:
                        processed_docs.append(text.strip())
                
                if not processed_docs:
                    logger.warning("⚠️ Нет валидных документов для добавления")
                    return False
                
                # Генерируем embeddings
                if not self.embeddings_service:
                    logger.error("❌ Embeddings service не инициализирован")
                    return False
                
                embeddings = self.embeddings_service.embed_batch(processed_docs)
                
                if not embeddings or len(embeddings) != len(processed_docs):
                    logger.error("❌ Ошибка при генерации embeddings")
                    return False
                
                # Генерируем IDs
                ids = [str(uuid.uuid4()) for _ in processed_docs]
                
                # Метаданные
                metadatas = [
                    {
                        "source": source,
                        "timestamp": datetime.now().isoformat(),
                        "length": len(doc)
                    }
                    for doc in processed_docs
                ]
                
                # Добавляем в Chroma (это синхронная операция)
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=processed_docs,
                    metadatas=metadatas
                )
                
                logger.info(f"✅ Добавлено документов: {len(processed_docs)}")
                return True
            
            except Exception as e:
                logger.error(f"❌ Ошибка добавления документов: {e}", exc_info=True)
                return False

    def search(self, query: str, top_k: int = 5) -> str:
        """Поиск в БД с фильтрацией и форматированием в строку"""
        try:
            if not query or not query.strip():
                return ""

            # Проверка на пустую БД
            if self.collection.count() == 0:
                return ""

            query_embedding = self.embeddings_service.embed([query])
            if not query_embedding or not query_embedding[0]:
                return ""
                
            query_embedding = query_embedding[0]
            
            # Поиск
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )
            
            if not results or not results['documents'] or not results['documents'][0]:
                return ""
            
            # Сборка контекста с фильтрацией
            valid_docs = []
            
            for i, doc in enumerate(results['documents'][0]):
                distance = results['distances'][0][i] if 'distances' in results else 0
                similarity = 1 - distance
                
                # ФИЛЬТР: Только релевантные документы (> 0.4 для cosine distance)
                # Если используешь nomic-embed-text, там distance может быть маленьким, similarity высоким.
                # Поставь 0.3-0.4 для начала, это безопасно.
                if similarity >= 0.35: 
                    meta = results['metadatas'][0][i] if 'metadatas' in results else {}
                    source = meta.get('source', 'unknown')
                    valid_docs.append(f"[Источник: {source}]\n{doc}")
                else:
                    logger.debug(f"🔍 Документ пропущен (similarity={similarity:.3f})")

            return "\n\n".join(valid_docs)

        except Exception as e:
            logger.error(f"❌ Ошибка поиска БД: {e}")
            return ""

    async def delete_old_documents(self, days: int = 60) -> int:
        """Удалить документы старше N дней (с блокировкой для одновременных запросов)"""
        async with self.write_lock:
            try:
                cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

                # Получаем все документы и фильтруем
                all_docs = self.collection.get()

                if not all_docs or not all_docs.get('ids'):
                    return 0

                old_ids = []
                for i, metadata in enumerate(all_docs.get('metadatas', [])):
                    if metadata.get('timestamp', '') < cutoff_date:
                        old_ids.append(all_docs['ids'][i])

                if old_ids:
                    self.collection.delete(ids=old_ids)
                    logger.info(f"✅ Удалено {len(old_ids)} документов (старше {days} дней)")
                    return len(old_ids)

                logger.debug(f"ℹ️ Нет документов для удаления")
                return 0
            
            except Exception as e:
                logger.error(f"❌ Ошибка удаления документов: {e}", exc_info=True)
                return 0

    def get_stats(self) -> dict:
        """Получить статистику БД"""
        try:
            total = self.collection.count()
            return {
                'total_documents': total,
                'collection_name': CHROMA_COLLECTION_NAME,
                'embedding_model': EMBEDDING_MODEL,
                'path': CHROMA_PATH,
            }
        except Exception as e:
            logger.error(f"❌ Ошибка статистики: {e}", exc_info=True)
            return {
                'total_documents': 0,
                'collection_name': CHROMA_COLLECTION_NAME,
                'embedding_model': EMBEDDING_MODEL,
            }

    def clear(self) -> bool:
        """Очистить БД полностью"""
        try:
            all_docs = self.collection.get()
            if all_docs and all_docs.get('ids'):
                self.collection.delete(ids=all_docs['ids'])
                logger.info(f"✅ БД очищена ({len(all_docs['ids'])} документов)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки: {e}", exc_info=True)
            return False

    def get_collection_info(self) -> dict:
        """Получить детальную информацию о коллекции"""
        try:
            all_docs = self.collection.get()
            
            if not all_docs or not all_docs.get('ids'):
                return {
                    'total': 0,
                    'sources': {},
                    'oldest': None,
                    'newest': None,
                }
            
            # Считаем по источникам
            sources = {}
            timestamps = []
            
            for metadata in all_docs.get('metadatas', []):
                source = metadata.get('source', 'unknown')
                sources[source] = sources.get(source, 0) + 1
                
                ts = metadata.get('timestamp')
                if ts:
                    timestamps.append(ts)
            
            timestamps.sort()
            
            return {
                'total': len(all_docs['ids']),
                'sources': sources,
                'oldest': timestamps[0] if timestamps else None,
                'newest': timestamps[-1] if timestamps else None,
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка информации: {e}")
            return {}