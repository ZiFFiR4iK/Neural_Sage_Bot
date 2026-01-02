#!/usr/bin/env python3

"""
🔧 config.py - ДИНАМИЧЕСКИЙ КОНФИГ С .env
Без дублирований и ошибок
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📂 PATHS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT = Path(__file__).parent
LOGS_PATH = PROJECT_ROOT / "logs"
LOGS_PATH.mkdir(exist_ok=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🤖 TELEGRAM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в .env!")

TELEGRAM_BOT_TOKEN = TELEGRAM_TOKEN
TELEGRAM_BOT_DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🦙 OLLAMA / LLM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "neural-chat")
LLM_NUM_PREDICT = int(os.getenv("LLM_NUM_PREDICT", "2000"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_TOP_K = int(os.getenv("LLM_TOP_K", "3"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 РЕЖИМЫ - ДИНАМИЧЕСКИЙ КОНФИГ ИЗ .env
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_mode_config(env_var: str, default: dict) -> dict:
    """Парсить JSON конфиг режима из .env"""
    value = os.getenv(env_var)
    if not value:
        return default
    try:
        value = value.strip().strip("'\"")
        parsed = json.loads(value)
        return {**default, **parsed}
    except json.JSONDecodeError as e:
        print(f"⚠️ Ошибка парсинга {env_var}: {e}, используется дефолт")
        return default

_DEFAULT_SHORT = {
    "num_predict": 300,
    "temperature": 0.2,
    "top_k": 2,
    "db_search": True,
    "web_search": True,
    "web_search_results": 2,
}

_DEFAULT_DEFAULT = {
    "num_predict": 1000,
    "temperature": 0.5,
    "top_k": 3,
    "db_search": True,
    "web_search": True,
    "web_search_results": 3,
}

_DEFAULT_DETAILED = {
    "num_predict": 2000,
    "temperature": 0.7,
    "top_k": 5,
    "db_search": True,
    "web_search": True,
    "web_search_results": 5,
}

# ДИНАМИЧЕСКИЙ конфиг (из .env)
_DYNAMIC_MODES = {
    "short": _parse_mode_config("MODE_SHORT", _DEFAULT_SHORT),
    "default": _parse_mode_config("MODE_DEFAULT", _DEFAULT_DEFAULT),
    "detailed": _parse_mode_config("MODE_DETAILED", _DEFAULT_DETAILED),
}

# РАСШИРЕННЫЙ конфиг с метаданными для RAG
MODE_CONFIGS = {
    "short": {
        **_DYNAMIC_MODES["short"],
        "name": "Кратко",
        "description": "2-3 предложения",
        "target_length": 100,
        "min_length": 50,
        "max_length": 200,
    },
    "default": {
        **_DYNAMIC_MODES["default"],
        "name": "Нормально",
        "description": "800-1000 слов",
        "target_length": 900,
        "min_length": 500,
        "max_length": 1500,
    },
    "detailed": {
        **_DYNAMIC_MODES["detailed"],
        "name": "Подробно",
        "description": "1500-2500 слов",
        "target_length": 2000,
        "min_length": 1200,
        "max_length": 3500,
    },
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌐 WEB SEARCH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WEB_SEARCH_TIMEOUT = int(os.getenv("WEB_SEARCH_TIMEOUT", "8"))
WEB_SEARCH_RESULTS = int(os.getenv("WEB_SEARCH_RESULTS", "5"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📊 LOGGING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE = LOGS_PATH / "bot.log"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⏱️ TIMEOUTS & RETRIES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))
QUEUE_FILE = PROJECT_ROOT / "pending_messages.json"
QUEUE_AUTO_RETRY = os.getenv("QUEUE_AUTO_RETRY", "true").lower() == "true"
QUEUE_RETRY_DELAY = int(os.getenv("QUEUE_RETRY_DELAY", "300"))
TELEGRAM_RETRY_ATTEMPTS = int(os.getenv("TELEGRAM_RETRY_ATTEMPTS", "3"))
TELEGRAM_RETRY_DELAY = int(os.getenv("TELEGRAM_RETRY_DELAY", "2"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📚 CHROMA / DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHROMA_PATH = os.getenv("CHROMA_PATH", "chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "documents")
CHROMA_SEARCH_TOPK = int(os.getenv("CHROMA_SEARCH_TOPK", "5"))
CHROMA_SIMILARITY_THRESHOLD = float(os.getenv("CHROMA_SIMILARITY_THRESHOLD", "0.6"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
EMBEDDING_CACHE_SIZE = int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
DB_AUTO_ADD_SOURCES = os.getenv("DB_AUTO_ADD_SOURCES", "true").lower() == "true"
DB_CLEANUP_DAYS = int(os.getenv("DB_CLEANUP_DAYS", "60"))
DB_AUTO_CLEANUP = os.getenv("DB_AUTO_CLEANUP", "false").lower() == "true"

print(f"✅ CHROMA: path={CHROMA_PATH}, collection={CHROMA_COLLECTION_NAME}, topk={CHROMA_SEARCH_TOPK}")
print(f"✅ EMBEDDINGS: model={EMBEDDING_MODEL}, batch_size={EMBEDDING_BATCH_SIZE}")
print(f"✅ DB: similarity_threshold={CHROMA_SIMILARITY_THRESHOLD}, auto_add={DB_AUTO_ADD_SOURCES}")
print(f"✅ EMBEDDING CACHE: size={EMBEDDING_CACHE_SIZE}")

# ═══════════════════════════════════════════════════════════════════════
# 🛡️ VALIDATION CONFIG - параметры многоуровневой валидации
# ═══════════════════════════════════════════════════════════════════════

VALIDATION_CONFIG = {
    # Контекст (ЭТАП 2)
    'min_context_length': 50,           # Минимум символов контекста
    'min_content_lines': 3,             # Минимум содержательных строк в Web
    'min_db_length': 50,                # Минимум символов из DB
    
    # Ответ (ЭТАП 4)
    'min_response_length': 30,          # Минимум длина ответа (символов)
    'warn_short_response': 100,         # Warning если меньше этого
    'min_overlap': 0.1,                 # Минимум пересечение слов (10%)
    
    # Поиск
    'min_web_content_chars': 100,       # Минимум символов в Web результатах
    
    # Логирование
    'log_full_prompt': True,            # Логировать полный промпт в DEBUG
    'log_context': True,                # Логировать полный контекст в DEBUG
}

# ═══════════════════════════════════════════════════════════════════════
# 🎨 ФУНКЦИИ ДЛЯ ВЫВОДА КОНФИГА
# ═══════════════════════════════════════════════════════════════════════

def print_config():
    """Вывести конфиг при старте"""
    print("\n" + "=" * 70)
    print("🤖 WEB-FIRST RAG BOT - КОНФИГУРАЦИЯ")
    print("=" * 70)
    print(f"🦙 LLM: {LLM_MODEL} @ {OLLAMA_HOST}")
    print(f"📊 Web Search: Timeout={WEB_SEARCH_TIMEOUT}s, Results={WEB_SEARCH_RESULTS}")
    print(f"🌡️ LLM Baseline: Temp={LLM_TEMPERATURE}, Top-K={LLM_TOP_K}")
    
    if TELEGRAM_TOKEN:
        print(f"✅ Telegram Token: {'***' + TELEGRAM_TOKEN[-6:]}")
    else:
        print("❌ Telegram Token: НЕ УСТАНОВЛЕН!")
    
    print("\n📋 РЕЖИМЫ (переопределяются через .env):")
    for mode_name, config in MODE_CONFIGS.items():
        print(f"\n [{mode_name.upper()}]")
        print(f" • Описание: {config['description']}")
        print(f" • Макс токенов: {config['num_predict']}")
        print(f" • Температура: {config['temperature']}")
        print(f" • Top-K: {config['top_k']}")
        print(f" • Поиск в БД: {'✅' if config.get('db_search') else '❌'}")
        print(f" • Веб-поиск: {'✅' if config.get('web_search') else '❌'}")
        print(f" • Целевой размер: {config.get('target_length', 'N/A')} символов")
    
    print("\n🛡️ ВАЛИДАЦИЯ:")
    print(f" • Min context: {VALIDATION_CONFIG['min_context_length']} chars")
    print(f" • Min overlap: {VALIDATION_CONFIG['min_overlap']*100:.0f}%")
    print(f" • Log prompts: {'✅' if VALIDATION_CONFIG['log_full_prompt'] else '❌'}")
    
    print("=" * 70 + "\n")