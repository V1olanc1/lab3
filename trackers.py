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

class TrackerManager:
    """Менеджер трекеров: хранит состояния, валидирует, даёт похвалу."""

    def __init__(self, today: Optional[dt.date] = None) -> None:
        self.today = today or dt.date.today()

        self.configs: Dict[str, TrackerConfig] = {
            "water": TrackerConfig(
                key="water",
                title="Вода",
                unit="стаканов",
                step=1,
                default_goal=8,
                min_goal=1,
                max_goal=30,
                max_value=200,
                congrats_title="Отлично!",
                congrats_template="Ты выпил(а) норму воды: {goal} стаканов.\nТак держать!",
            ),
            "steps": TrackerConfig(
                key="steps",
                title="Шаги",
                unit="шагов",
                step=500,
                default_goal=10_000,
                min_goal=1_000,
                max_goal=50_000,
                max_value=200_000,
                congrats_title="Круто!",
                congrats_template="Норма шагов выполнена: {goal}.\nОтличная активность!",
            ),
            "sleep": TrackerConfig(
                key="sleep",
                title="Сон",
                unit="минут",
                step=30,
                default_goal=8 * 60,      # 8:00
                min_goal=0,
                max_goal=24 * 60,
                max_value=24 * 60,
                congrats_title="Супер!",
                congrats_template="Норма сна выполнена: {goal}.\nХороший сон — это важно!",
                is_sleep=True,
            ),
            "pages": TrackerConfig(
                key="pages",
                title="Чтение",
                unit="страниц",
                step=5,
                default_goal=30,
                min_goal=1,
                max_goal=1000,
                max_value=10_000,
                congrats_title="Молодец!",
                congrats_template="Норма чтения выполнена: {goal} страниц.\nОтличная привычка!",
            ),
        }

        self.state: Dict[str, TrackerState] = {
            k: TrackerState(date=self.today, value=0, goal=cfg.default_goal)
            for k, cfg in self.configs.items()
        }

    def reset_if_new_day(self) -> bool:
        """Сбросить значения, если наступил новый день. Возвращает True, если были изменения."""
        changed = False
        for key, st in self.state.items():
            if st.date != self.today:
                st.date = self.today
                st.value = 0
                st.congrats_shown = False
                changed = True
        return changed

    def change_value(self, key: str, delta: int) -> Optional[tuple[str, str]]:
        """Изменить значение на delta. Вернёт похвалу (title, msg), если норма достигнута впервые."""
        self._ensure_today(key)
        cfg = self.configs[key]
        st = self.state[key]

        st.value = clamp(st.value + delta, 0, cfg.max_value)

        if st.value < st.goal:
            st.congrats_shown = False

        return self._maybe_congratulate(key)

    def set_value(self, key: str, value: int) -> Optional[tuple[str, str]]:
        """Установить точное значение (для сна удобно)."""
        self._ensure_today(key)
        cfg = self.configs[key]
        st = self.state[key]

        st.value = clamp(value, 0, cfg.max_value)

        if st.value < st.goal:
            st.congrats_shown = False

        return self._maybe_congratulate(key)

    def set_goal(self, key: str, goal: int) -> Optional[tuple[str, str]]:
        """Установить норму."""
        self._ensure_today(key)
        cfg = self.configs[key]
        st = self.state[key]

        st.goal = clamp(goal, cfg.min_goal, cfg.max_goal)

        if st.value < st.goal:
            st.congrats_shown = False

        return self._maybe_congratulate(key)

    def reset(self, key: str) -> None:
        """Сбросить конкретный трекер на 0."""
        self._ensure_today(key)
        st = self.state[key]
        st.value = 0
        st.congrats_shown = False

    def format_value(self, key: str) -> str:
        """Формат value для UI."""
        cfg = self.configs[key]
        st = self.state[key]
        if cfg.is_sleep:
            return minutes_to_hhmm(st.value)
        return str(st.value)

    def format_goal(self, key: str) -> str:
        """Формат goal для UI."""
        cfg = self.configs[key]
        st = self.state[key]
        if cfg.is_sleep:
            return minutes_to_hhmm(st.goal)
        return str(st.goal)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация трекеров."""
        trackers: Dict[str, Any] = {}
        for key, st in self.state.items():
            trackers[key] = {
                "date": st.date.isoformat(),
                "value": st.value,
                "goal": st.goal,
                "congrats_shown": st.congrats_shown,
            }
        return {"version": DATA_VERSION, "trackers": trackers}

    def load_from_dict(self, data: Any) -> None:
        """Загрузка трекеров из dict (с защитой от мусора)."""
        if not isinstance(data, dict):
            return

        root = data.get("trackers")
        if not isinstance(root, dict):
            return

        for key, cfg in self.configs.items():
            raw = root.get(key)
            if not isinstance(raw, dict):
                continue

            date_str = str(raw.get("date", "")).strip()
            try:
                date_val = dt.date.fromisoformat(date_str) if date_str else self.today
            except ValueError:
                date_val = self.today

            value = safe_int(raw.get("value"), 0)
            goal = safe_int(raw.get("goal"), cfg.default_goal)
            congrats = bool(raw.get("congrats_shown", False))

            st = self.state[key]
            st.date = date_val
            st.value = clamp(value, 0, cfg.max_value)
            st.goal = clamp(goal, cfg.min_goal, cfg.max_goal)
            st.congrats_shown = congrats

    def _ensure_today(self, key: str) -> None:
        st = self.state[key]
        if st.date != self.today:
            st.date = self.today
            st.value = 0
            st.congrats_shown = False

    def _maybe_congratulate(self, key: str) -> Optional[tuple[str, str]]:
        cfg = self.configs[key]
        st = self.state[key]

        if st.congrats_shown or st.goal <= 0:
            return None
        if st.value < st.goal:
            return None

        st.congrats_shown = True
        goal_str = minutes_to_hhmm(st.goal) if cfg.is_sleep else str(st.goal)
        msg = cfg.congrats_template.format(goal=goal_str)
        return cfg.congrats_title, msg