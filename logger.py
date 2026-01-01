#!/usr/bin/env python3

"""

📝 ЛОГИРОВАНИЕ С ЦВЕТАМИ И СМАЙЛИКАМИ

Единая система логирования для всего проекта

"""

import logging
import sys
from config import LOG_LEVEL, LOG_FORMAT, LOG_FILE

# ANSI цвета для консоли
class _ColoredFormatter(logging.Formatter):
    """Форматер с цветами для консоли"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Голубой
        'INFO': '\033[92m',       # Зелёный
        'WARNING': '\033[93m',    # Жёлтый
        'ERROR': '\033[91m',      # Красный
        'CRITICAL': '\033[41m',   # Красный фон
        'RESET': '\033[0m',
    }
    
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '✅',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨',
    }
    
    def format(self, record):
        emoji = self.EMOJIS.get(record.levelname, '•')
        color = self.COLORS.get(record.levelname, '')
        reset = self.COLORS['RESET']
        
        formatted = f"[{record.asctime}] {emoji} {record.getMessage()}"
        formatted = f"{color}{formatted}{reset}"
        
        return formatted

# Создаём корневой логгер
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)

# Обработчик для ФАЙЛА (чистый текст БЕЗ цветов)
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(LOG_LEVEL)
file_formatter = logging.Formatter(LOG_FORMAT)
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler)

# Обработчик для КОНСОЛИ (с цветами и смайликами)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(LOG_LEVEL)
console_formatter = _ColoredFormatter(LOG_FORMAT)
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """Получить логгер для модуля"""
    return logging.getLogger(name)