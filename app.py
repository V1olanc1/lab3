from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

from trackers import TrackerManager, hhmm_to_minutes

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

    def _create_tasks_list(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))

        ttk.Label(card, text="Список задач", style="Header.TLabel").pack(anchor=tk.W)

        frame = ttk.Frame(card)
        frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.tasks_listbox = tk.Listbox(
            frame,
            relief=tk.FLAT,
            highlightthickness=0,
            activestyle="none",
            selectbackground=PRIMARY_COLOR,
            selectforeground="white",
            bg=CARD_BACKGROUND,
        )
        self.tasks_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tasks_listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tasks_listbox.config(yscrollcommand=scroll.set)

        self.tasks_listbox.bind("<<ListboxSelect>>", self.on_task_selected)

    def _create_task_form(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 0))

        ttk.Label(card, text="Детали задачи", style="Header.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )

        ttk.Label(card, text="Время (чч:мм):").grid(row=1, column=0, sticky="w", pady=4)
        self.time_entry = ttk.Entry(card, width=10)
        self.time_entry.grid(row=1, column=1, sticky="we", pady=4)

        ttk.Label(card, text="Название:").grid(row=2, column=0, sticky="w", pady=4)
        self.title_entry = ttk.Entry(card)
        self.title_entry.grid(row=2, column=1, sticky="we", pady=4)

        ttk.Label(card, text="Описание:").grid(row=3, column=0, sticky="nw", pady=4)

        desc_frame = ttk.Frame(card, style="Card.TFrame")
        desc_frame.grid(row=3, column=1, sticky="nsew", pady=4)

        self.description_text = tk.Text(
            desc_frame,
            height=8,
            wrap=tk.WORD,
            relief=tk.FLAT,
            highlightthickness=0,
            bg=CARD_BACKGROUND,
        )
        self.description_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        desc_scroll = ttk.Scrollbar(desc_frame, orient=tk.VERTICAL, command=self.description_text.yview)
        desc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.description_text.config(yscrollcommand=desc_scroll.set)

        self.completed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(card, text="Задача выполнена", variable=self.completed_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="e")

        ttk.Button(buttons, text="Добавить", style="Accent.TButton", command=self.add_task).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(buttons, text="Изменить", style="Accent.TButton", command=self.edit_task).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(buttons, text="Удалить", command=self.delete_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Очистить форму", command=self.clear_form).pack(side=tk.LEFT, padx=4)

        card.columnconfigure(1, weight=1)
        card.rowconfigure(3, weight=1)

    def _create_trackers_panel(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(5, 0))

        ttk.Label(card, text="Трекеры", style="Header.TLabel").pack(anchor=tk.W)

        notebook = ttk.Notebook(card)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        # вкладки в цикле по конфигам
        for key, cfg in self.tracker_mgr.configs.items():
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=cfg.title)
            if cfg.is_sleep:
                self._build_sleep_tab(tab, key)
            else:
                self._build_counter_tab(tab, key)

    def _build_counter_tab(self, tab: ttk.Frame, key: str) -> None:
        cfg = self.tracker_mgr.configs[key]

        text_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=text_var).pack(anchor=tk.W)

        bar = ttk.Progressbar(tab, orient=tk.HORIZONTAL, mode="determinate")
        bar.pack(fill=tk.X, pady=(6, 10))

        row = ttk.Frame(tab)
        row.pack(fill=tk.X)

        ttk.Button(row, text=f"−{cfg.step}", command=lambda: self._tracker_delta(key, -cfg.step)).pack(
            side=tk.LEFT
        )
        ttk.Button(row, text=f"+{cfg.step}", command=lambda: self._tracker_delta(key, cfg.step)).pack(
            side=tk.LEFT, padx=(6, 12)
        )

        ttk.Label(row, text="Норма:").pack(side=tk.LEFT)

        goal_var = tk.IntVar(value=self.tracker_mgr.state[key].goal)
        spin_cls = getattr(ttk, "Spinbox", tk.Spinbox)
        spin = spin_cls(
            row,
            from_=cfg.min_goal,
            to=cfg.max_goal,
            increment=max(1, cfg.step),
            width=8,
            textvariable=goal_var,
            command=lambda: self._apply_goal_counter(key),
        )
        spin.pack(side=tk.LEFT, padx=6)
        spin.bind("<Return>", lambda _e: self._apply_goal_counter(key))
        spin.bind("<FocusOut>", lambda _e: self._apply_goal_counter(key))

        ttk.Button(row, text="Сброс", command=lambda: self._reset_tracker(key)).pack(side=tk.RIGHT)

        self.tracker_ui[key] = {"text": text_var, "bar": bar, "goal": goal_var}

    def _build_sleep_tab(self, tab: ttk.Frame, key: str) -> None:
        text_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=text_var).pack(anchor=tk.W)

        bar = ttk.Progressbar(tab, orient=tk.HORIZONTAL, mode="determinate")
        bar.pack(fill=tk.X, pady=(6, 10))

        row1 = ttk.Frame(tab)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text="Сон (чч:мм):").pack(side=tk.LEFT)
        value_var = tk.StringVar(value=self.tracker_mgr.format_value(key))
        ttk.Entry(row1, width=8, textvariable=value_var).pack(side=tk.LEFT, padx=6)

        ttk.Button(row1, text="Установить", command=lambda: self._set_sleep_value(key)).pack(
            side=tk.LEFT
        )

        ttk.Button(row1, text="+30м", command=lambda: self._tracker_delta(key, 30)).pack(
            side=tk.LEFT, padx=(10, 0)
        )
        ttk.Button(row1, text="−30м", command=lambda: self._tracker_delta(key, -30)).pack(
            side=tk.LEFT, padx=6
        )

        row2 = ttk.Frame(tab)
        row2.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(row2, text="Норма (чч:мм):").pack(side=tk.LEFT)
        goal_var = tk.StringVar(value=self.tracker_mgr.format_goal(key))
        ttk.Entry(row2, width=8, textvariable=goal_var).pack(side=tk.LEFT, padx=6)

        ttk.Button(row2, text="Применить", command=lambda: self._apply_sleep_goal(key)).pack(
            side=tk.LEFT
        )
        ttk.Button(row2, text="Сброс", command=lambda: self._reset_tracker(key)).pack(side=tk.RIGHT)

        self.tracker_ui[key] = {
            "text": text_var,
            "bar": bar,
            "value": value_var,
            "goal_hhmm": goal_var,
        }

    def _show_congrats(self, congrats: Optional[Tuple[str, str]]) -> None:
        if congrats:
            title, msg = congrats
            messagebox.showinfo(title, msg)

    def _tracker_delta(self, key: str, delta: int) -> None:
        try:
            congrats = self.tracker_mgr.change_value(key, delta)
            self._show_congrats(congrats)
            self._refresh_tracker_ui(key)
            self._save_all()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _reset_tracker(self, key: str) -> None:
        try:
            if not messagebox.askyesno("Сброс", "Сбросить трекер на 0?"):
                return
            self.tracker_mgr.reset(key)
            self._refresh_tracker_ui(key)
            self._save_all()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _apply_goal_counter(self, key: str) -> None:
        try:
            goal_var = self.tracker_ui[key]["goal"]
            congrats = self.tracker_mgr.set_goal(key, int(goal_var.get()))
            self._show_congrats(congrats)
            self._refresh_tracker_ui(key)
            self._save_all()
            self.status_var.set("Норма обновлена.")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _set_sleep_value(self, key: str) -> None:
        try:
            raw = str(self.tracker_ui[key]["value"].get())
            minutes = hhmm_to_minutes(raw)
            congrats = self.tracker_mgr.set_value(key, minutes)
            self._show_congrats(congrats)
            self._refresh_tracker_ui(key)
            self._save_all()
            self.status_var.set("Сон обновлён.")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _apply_sleep_goal(self, key: str) -> None:
        try:
            raw = str(self.tracker_ui[key]["goal_hhmm"].get())
            minutes = hhmm_to_minutes(raw)
            congrats = self.tracker_mgr.set_goal(key, minutes)
            self._show_congrats(congrats)
            self._refresh_tracker_ui(key)
            self._save_all()
            self.status_var.set("Норма сна обновлена.")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def _refresh_tracker_ui(self, key: str) -> None:
        cfg = self.tracker_mgr.configs[key]
        st = self.tracker_mgr.state[key]
        ui = self.tracker_ui[key]

        if cfg.is_sleep:
            ui["text"].set(f"{self.tracker_mgr.format_value(key)} / {self.tracker_mgr.format_goal(key)}")
            ui["bar"]["maximum"] = max(1, st.goal)
            ui["bar"]["value"] = min(st.value, st.goal)
            ui["value"].set(self.tracker_mgr.format_value(key))
            ui["goal_hhmm"].set(self.tracker_mgr.format_goal(key))
            return

        ui["text"].set(f"{st.value} / {st.goal} {cfg.unit}")
        ui["bar"]["maximum"] = max(1, st.goal)
        ui["bar"]["value"] = min(st.value, st.goal)
        ui["goal"].set(st.goal)

    def _refresh_all_trackers_ui(self) -> None:
        for key in self.tracker_mgr.configs.keys():
            self._refresh_tracker_ui(key)