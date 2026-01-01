#!/usr/bin/env python3
"""
MESSAGE FORMATTER - очищает ответы LLM для Telegram (plain text режим)
Удаляет технические детали, избегает проблем с разметкой.
"""

import re
from logger import get_logger

logger = get_logger(__name__)


def format_response(text: str) -> str:
    """
    Очищает ответ для plain text отправки в Telegram.
    Не добавляет Markdown разметку - просто удаляет мусор.
    """
    if not text:
        return ""
    
    # Удаляем служебные метаданные
    text = text.replace('📚 ИЗ БАЗЫ ЗНАНИЙ:', '')
    text = text.replace('🌐 ИЗ ИНТЕРНЕТА:', '')
    text = text.replace('Источник:', '')
    
    # Удаляем повторяющиеся пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Удаляем странные символы
    text = text.replace('---', '-')
    
    return text.strip()


def clean_response_for_telegram(text: str, max_length: int = 4000) -> str:
    """
    Финальная очистка перед отправкой:
    1. Удаляет технические детали
    2. Обрезает по макс длине
    3. НЕ добавляет Markdown
    """
    if not text:
        return ""

    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # Удаляем технические метаданные
        if 'подобие:' in line.lower() or 'similarity:' in line.lower():
            continue
        if 'результаты из' in line.lower() or 'results from' in line.lower():
            continue
        if 'источник:' in line.lower() and 'http' in line.lower():
            # Оставляем ссылки как есть, но без форматирования
            line = line.replace('https://', 'https://').replace('http://', 'http://')
        
        cleaned_lines.append(line)

    result = '\n'.join(cleaned_lines).strip()

    # Обрезаем если слишком длинно
    if len(result) > max_length:
        result = result[:max_length]
        # Ищем последний перевод строки для красивого обреза
        last_newline = result.rfind('\n')
        if last_newline > max_length * 0.8:
            result = result[:last_newline]
        # Добавляем многоточие
        result += "\n\n[Текст обрезан из-за ограничения длины]"

    return result


def escape_telegram_special_chars(text: str) -> str:
    """
    Экранирует специальные символы для plain text.
    (На случай если понадобится)
    """
    # В plain text mode не нужно экранировать
    return text