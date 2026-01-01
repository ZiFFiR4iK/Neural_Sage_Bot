#!/usr/bin/env python3
"""
KEYBOARDS - Inline и Reply клавиатуры с кнопками
"""

from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_persistent_keyboard():
    """Постоянная клавиатура внизу экрана: режимы + справка"""
    keyboard = [
        [
            KeyboardButton("🟢 Кратко"),
            KeyboardButton("🟡 Нормально"),
            KeyboardButton("🔴 Подробно"),
        ],
        [
            KeyboardButton("📚 Справка"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def get_back_button_keyboard():
    """Кнопка назад"""
    keyboard = [
        [
            KeyboardButton("⬅️ Назад"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)