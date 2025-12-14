from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

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

    def _init_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=10, family="Segoe UI")

        style.configure("TFrame", background=BACKGROUND_COLOR)
        style.configure("Card.TFrame", background=CARD_BACKGROUND)
        style.configure("TLabel", background=BACKGROUND_COLOR, foreground="#222")
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("TEntry", padding=4)
        style.configure("TButton", padding=(8, 4))
        style.configure(
            "Accent.TButton",
            padding=(10, 5),
            foreground="#ffffff",
            background=PRIMARY_COLOR,
        )
        style.map(
            "Accent.TButton",
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
            background=[("!disabled", PRIMARY_COLOR), ("pressed", PRIMARY_DARK), ("active", PRIMARY_DARK)],
        )

    def _create_menu(self) -> None:
        main_menu = tk.Menu(self)

        file_menu = tk.Menu(main_menu, tearoff=0)
        file_menu.add_command(label="Выход", command=self.on_exit)
        main_menu.add_cascade(label="Файл", menu=file_menu)

        settings_menu = tk.Menu(main_menu, tearoff=0)
        settings_menu.add_command(label="Размер окна...", command=self.change_window_size)
        main_menu.add_cascade(label="Настройки", menu=settings_menu)

        help_menu = tk.Menu(main_menu, tearoff=0)
        help_menu.add_command(label="О программе", command=self.show_about)
        main_menu.add_cascade(label="Справка", menu=help_menu)

        self.config(menu=main_menu)

    def _create_main_widgets(self) -> None:
        header = tk.Frame(self, bg=PRIMARY_COLOR)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="Планировщик дня",
            bg=PRIMARY_COLOR,
            fg="white",
            font=("Segoe UI", 16, "bold"),
        ).pack(side=tk.LEFT, padx=16, pady=10)

        tk.Label(
            header,
            text=f"Сегодня: {self.today.strftime('%d.%m.%Y')}",
            bg=PRIMARY_COLOR,
            fg="white",
            font=("Segoe UI", 10),
        ).pack(side=tk.RIGHT, padx=16)

        content = ttk.Frame(self, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=3)
        content.rowconfigure(1, weight=2)

        self._create_tasks_list(content)
        self._create_trackers_panel(content)
        self._create_task_form(content)

        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = tk.Frame(self, bg=STATUS_BG)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(status_bar, textvariable=self.status_var, bg=STATUS_BG, anchor="w").pack(
            fill=tk.X, padx=10, pady=2
        )
