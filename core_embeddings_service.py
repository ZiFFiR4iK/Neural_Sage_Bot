#!/usr/bin/env python3

"""
🔢 EMBEDDINGS SERVICE - Генерация embeddings через Ollama
"""

import requests
from config import OLLAMA_HOST, EMBEDDING_MODEL, REQUEST_TIMEOUT, EMBEDDING_CACHE_SIZE
from logger import get_logger

logger = get_logger(__name__)

class EmbeddingsService:
    """Сервис для генерации embeddings"""

    def __init__(self):
        """Инициализация"""
        logger.info(f"🔢 Инициализирую EmbeddingsService (модель={EMBEDDING_MODEL})...")
        self.host = OLLAMA_HOST
        self.model = EMBEDDING_MODEL
        self.endpoint = f"{self.host}/api/embeddings"
        
        # LRU cache для часто используемых embeddings
        self._embed_cache = {}
        self.cache_size = EMBEDDING_CACHE_SIZE
        logger.info(f"✅ EmbeddingsService инициализирована")

    def embed(self, texts: list) -> list:
        """Генерирует embeddings для списка текстов"""
        if not texts:
            return []
        
        embeddings = [None] * len(texts)  # Заранее создаем список нужного размера
        uncached = []
        uncached_indices = []
        
        # Проверяем кэш
        for i, text in enumerate(texts):
            text_hash = hash(text)
            if text_hash in self._embed_cache:
                embeddings[i] = self._embed_cache[text_hash]
            else:
                uncached.append(text)
                uncached_indices.append(i)
        
        # Генерируем embeddings для некэшированных текстов
        if uncached:
            new_embeddings = self._call_ollama(uncached)
            
            # Добавляем в результат и кэш
            for idx, embedding in zip(uncached_indices, new_embeddings):
                text_hash = hash(texts[idx])
                self._embed_cache[text_hash] = embedding
                embeddings[idx] = embedding  # Вставляем в правильную позицию
                
                # Ограничиваем размер кэша
                if len(self._embed_cache) > self.cache_size:
                    oldest_key = next(iter(self._embed_cache))
                    del self._embed_cache[oldest_key]
        
        return embeddings

    def embed_batch(self, texts: list, batch_size: int = 32) -> list:
        """Генерирует embeddings батчами"""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.embed(batch)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings

    def _call_ollama(self, texts: list) -> list:
        """Вызывает Ollama API для генерации embeddings"""
        try:
            embeddings = []
            for text in texts:
                payload = {
                    "model": self.model,
                    "prompt": text,
                }
                
                try:
                    response = requests.post(
                        self.endpoint,
                        json=payload,
                        timeout=REQUEST_TIMEOUT,
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        embedding = result.get("embedding", [])
                        embeddings.append(embedding)
                    else:
                        logger.warning(f"⚠️ Embeddings API ошибка: {response.status_code}")
                        embeddings.append([0.0] * 384)  # Дефолтный embedding
                
                except Exception as e:
                    logger.error(f"❌ Ошибка embeddings: {e}")
                    embeddings.append([0.0] * 384)
            
            return embeddings
        
        except Exception as e:
            logger.error(f"❌ Критическая ошибка embeddings: {e}")
            return [[0.0] * 384 for _ in texts]

    def clear_cache(self):
        """Очистить кэш"""
        self._embed_cache.clear()
        logger.info("✅ Кэш embeddings очищен")