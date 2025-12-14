from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


import tkinter as tk
from trackers import TrackerManager

PRIMARY_COLOR = "#3f51b5"
PRIMARY_DARK = "#303f9f"
BACKGROUND_COLOR = "#f5f5f7"
CARD_BACKGROUND = "#ffffff"
STATUS_BG = "#e0e0e0"

DATA_FILE_NAME = "day_planner_data.json"


def get_storage_path() -> Path:
    try:
        base_dir = Path(__file__).resolve().parent
    except NameError:
        base_dir = Path.cwd()
    return base_dir / DATA_FILE_NAME


def parse_task_time(time_str: str) -> dt.time:
    return dt.datetime.strptime(time_str.strip(), "%H:%M").time()


@dataclass(order=True)
class Task:
    time: dt.time = field(compare=True)
    title: str = field(compare=False)
    description: str = field(compare=False)
    completed: bool = field(default=False, compare=False)

    def format_for_list(self) -> str:
        mark = "[✓]" if self.completed else "[ ]"
        return f"{mark} {self.time.strftime('%H:%M')} — {self.title}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time.strftime("%H:%M"),
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        time_value = parse_task_time(str(data.get("time", "")).strip())
        title = str(data.get("title", "")).strip()
        if not title:
            raise ValueError("Пустое название задачи.")
        return cls(
            time=time_value,
            title=title,
            description=str(data.get("description", "")),
            completed=bool(data.get("completed", False)),
        )
class DayPlannerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Планировщик дня")
        self.geometry("1000x650")
        self.minsize(780, 520)
        self.configure(bg=BACKGROUND_COLOR)

        self.storage_path = get_storage_path()
        self.today = dt.date.today()

        self.tasks: List[Task] = []
        self.tracker_mgr = TrackerManager(today=self.today)

        self.tracker_ui: Dict[str, Dict[str, Any]] = {}

        self._init_style()
        self._create_menu()
        self._create_main_widgets()

        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        self._load_all()
        if self.tracker_mgr.reset_if_new_day():
            self._save_all()

        self._refresh_tasks_list()
        self._refresh_all_trackers_ui()