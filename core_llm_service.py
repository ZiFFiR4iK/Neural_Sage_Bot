#!/usr/bin/env python3
"""
🦙 core/llm_service.py
"""

import re
import requests
from config import (
    OLLAMA_HOST,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TOP_K,
    REQUEST_TIMEOUT,
    MODE_CONFIGS,
)
from logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """LLM сервис с поддержкой динамических режимов и авто-дополнения ответа."""

    SYSTEM_PROMPT = """Ты полезный помощник AI на русском языке.

    ГЛАВНОЕ ПРАВИЛО: Всегда отвечай ТОЛЬКО на РУССКОМ языке. Никаких исключений.

    Если в вопросе английский текст - переводи его и отвечай по-русски.
    Если нужны примеры кода на английском - оставляй код как есть, но описание пиши на русском.

    Инструкции:
    1. Отвечай четко и по существу
    2. Используй предоставленный контекст если дан
    3. Структурируй ответ (заголовки, списки при необходимости)
    4. Если приводишь код или команды - оборачивай в ```python``` или ```bash```
    5. Будь вежлив и конструктивен
    6. КРИТИЧНО: ответ ПОЛНОСТЬЮ на русском языке!

    Язык: РУССКИЙ (обязательно)"""

    INCOMPLETE_THRESHOLD = 0.85
    MAX_CONTINUATION_RETRIES = 2

    def __init__(self):
        self.host = OLLAMA_HOST
        self.model = LLM_MODEL
        self.endpoint = f"{self.host}/api/generate"
        logger.info(f"✅ LLM инициализирована: {self.model} @ {self.host}")

    def _clean_answer(self, text: str) -> str:
        """Легкая очистка вывода модели."""
        if not text:
            return ""

        text = re.sub(r"\n\n\n+", "\n\n", text)
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        return text.strip()

    def _looks_incomplete(self, text: str, max_tokens: int) -> bool:
        """Проверяет, выглядит ли ответ незавершённым."""
        if not text:
            return False

        tail = text.strip()[-40:]
        proper_endings = (".", "!", "?", "```", "`", '"', "»", ")", "]", "}")

        if any(tail.endswith(e) for e in proper_endings):
            return False

        est_tokens = len(text) / 3.5
        ratio = est_tokens / max_tokens if max_tokens > 0 else 0.0

        if ratio > self.INCOMPLETE_THRESHOLD:
            logger.warning(
                f"⚠️ Ответ выглядит незавершённым ({ratio*100:.1f}% от лимита)"
            )
            return True

        return False

    def _call_ollama(
        self,
        full_prompt: str,
        max_tokens: int,
        temperature: float,
        top_k: int,
    ) -> str:
        """Внутренний вызов к Ollama API."""
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "num_predict": max_tokens,
            "temperature": temperature,
            "top_k": top_k,
        }

        logger.debug(
            f"🔍 DEBUG: LLM запрос (токенов={max_tokens}, temp={temperature}, top_k={top_k})"
        )

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()
            result = response.json()
            answer = (result.get("response") or "").strip()

            if answer:
                logger.info(
                    f"✅ LLM ответила ({len(answer)} символов)"
                )
            else:
                logger.warning("⚠️ LLM вернул пустой response")

            return answer

        except requests.exceptions.Timeout:
            logger.error("❌ Timeout: Ollama не отвечает")
            return ""
        except requests.exceptions.ConnectionError:
            logger.error("❌ ConnectionError: Ollama не запущена")
            return ""
        except Exception as e:
            logger.error(f"❌ Ошибка LLM: {e}")
            return ""

    def generate(self, prompt: str, context: str = "", mode: str = "default") -> str:
        """
        Генерировать ответ с динамическими параметрами режима.

        Args:
            prompt: основной вопрос
            context: контекст (из БД или веба)
            mode: "short", "default" или "detailed"

        Returns:
            str: ответ от LLM
        """
        try:
            if mode not in MODE_CONFIGS:
                logger.warning(f"⚠️ Неизвестный режим '{mode}', используем 'default'")
                mode = "default"

            cfg = MODE_CONFIGS.get(mode, {})
            max_tokens = int(cfg.get("num_predict", 600))
            top_k = int(cfg.get("top_k", LLM_TOP_K))
            temperature = float(cfg.get("temperature", LLM_TEMPERATURE))

            if mode == "short":
                max_tokens = min(max_tokens, 120)

            full_prompt = f"{self.SYSTEM_PROMPT}\n\n{prompt}"

            answer = self._call_ollama(
                full_prompt=full_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
            )

            if not answer:
                return ""

            answer = self._clean_answer(answer)

            # Continuation для DEFAULT и DETAILED, но НЕ для SHORT
            enable_continuation = mode in ["default", "detailed"]

            retries = 0
            while (
                enable_continuation
                and self._looks_incomplete(answer, max_tokens)
                and retries < self.MAX_CONTINUATION_RETRIES
            ):
                retries += 1
                logger.info(
                    f"🔄 Continuation {retries}/{self.MAX_CONTINUATION_RETRIES} (режим {mode})"
                )
                
                continuation_prompt = (
                    f"{self.SYSTEM_PROMPT}\n\n"
                    f"[Пользователь просит подробный ответ. "
                    f"Продолжи ответ естественно, без повторений. "
                    f"Если ответ уже закончен логично, просто скажи что он полный.]\n\n"
                    f"ПРЕДЫДУЩИЙ ОТВЕТ (может быть обрезан):\n{answer}"
                )
                
                continuation = self._call_ollama(
                    full_prompt=continuation_prompt,
                    max_tokens=max_tokens // 2,
                    temperature=temperature,
                    top_k=top_k,
                )
                
                if not continuation:
                    logger.warning("⚠️ Continuation вернул пустой ответ")
                    break
                
                continuation = self._clean_answer(continuation)
                
                # Проверяем что continuation не просто повторение старого текста
                if continuation.lower() in answer.lower() or len(continuation) < 50:
                    logger.info("ℹ️ Continuation повторил текст или слишком короткий, стопим")
                    break
                
                answer = f"{answer}\n\n{continuation}"
                logger.info(f"✅ Continuation: добавлено {len(continuation)} символов")

            if retries > 0:
                logger.info(
                    f"✅ Ответ готов ({len(answer)} символов, режим {mode})"
                )

            return answer

        except Exception as e:
            logger.error(f"❌ Ошибка LLM.generate: {e}")
            return ""