from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, Optional


DATA_VERSION = 1


def clamp(value: int, min_v: int, max_v: int) -> int:
    """Ограничение значения в диапазоне."""
    return max(min_v, min(max_v, value))


def safe_int(value: Any, default: int) -> int:
    """Безопасное преобразование к int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def minutes_to_hhmm(minutes: int) -> str:
    """Минуты -> 'H:MM'."""
    minutes = max(0, minutes)
    return f"{minutes // 60}:{minutes % 60:02d}"


def hhmm_to_minutes(text: str) -> int:
    """
    'H:MM' or 'HH:MM' -> minutes. Hours: 0..24, minutes: 0..59.
    """
    raw = text.strip()
    if not raw or ":" not in raw:
        raise ValueError("Ожидается формат ЧЧ:ММ (например 7:30 или 08:00).")

    parts = raw.split(":")
    if len(parts) != 2:
        raise ValueError("Ожидается формат ЧЧ:ММ.")

    try:
        hours = int(parts[0])
        mins = int(parts[1])
    except ValueError as exc:
        raise ValueError("Часы и минуты должны быть числами.") from exc

    if not (0 <= hours <= 24):
        raise ValueError("Часы должны быть в диапазоне 0..24.")
    if not (0 <= mins <= 59):
        raise ValueError("Минуты должны быть в диапазоне 0..59.")

    total = hours * 60 + mins
    if total > 24 * 60:
        raise ValueError("Значение не может быть больше 24:00.")
    return total

@dataclass(frozen=True)
class TrackerConfig:
    """Конфигурация трекера."""
    key: str
    title: str
    unit: str
    step: int
    default_goal: int
    min_goal: int
    max_goal: int
    max_value: int
    congrats_title: str
    congrats_template: str
    is_sleep: bool = False  # сон хранится в минутах, UI в HH:MM


@dataclass
class TrackerState:
    """Состояние трекера."""
    date: dt.date
    value: int
    goal: int
    congrats_shown: bool = False
