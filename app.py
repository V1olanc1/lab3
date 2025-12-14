"""
app.py
GUI: задачи планировщика + вкладки трекеров.
Сохранение в один JSON (задачи + трекеры), загрузка при старте.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
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
        header.pack(fill="x")

        tk.Label(
            header,
            text="Планировщик дня",
            bg=PRIMARY_COLOR,
            fg="white",
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=16, pady=10)

        tk.Label(
            header,
            text=f"Сегодня: {self.today.strftime('%d.%m.%Y')}",
            bg=PRIMARY_COLOR,
            fg="white",
            font=("Segoe UI", 10),
        ).pack(side="right", padx=16)

        content = ttk.Frame(self, padding=10)
        content.pack(fill="both", expand=True)

        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=3)
        content.rowconfigure(1, weight=2)

        self._create_tasks_list(content)
        self._create_trackers_panel(content)
        self._create_task_form(content)

        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = tk.Frame(self, bg=STATUS_BG)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self.status_var, bg=STATUS_BG, anchor="w").pack(
            fill="x", padx=10, pady=2
        )

    def _create_tasks_list(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))

        ttk.Label(card, text="Список задач", style="Header.TLabel").pack(anchor="w")

        frame = ttk.Frame(card)
        frame.pack(fill="both", expand=True, pady=(8, 0))

        self.tasks_listbox = tk.Listbox(
            frame,
            relief="flat",
            highlightthickness=0,
            activestyle="none",
            selectbackground=PRIMARY_COLOR,
            selectforeground="white",
            bg=CARD_BACKGROUND,
        )
        self.tasks_listbox.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tasks_listbox.yview)
        scroll.pack(side="right", fill="y")
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
            wrap="word",
            relief="flat",
            highlightthickness=0,
            bg=CARD_BACKGROUND,
        )
        self.description_text.pack(side="left", fill="both", expand=True)

        desc_scroll = ttk.Scrollbar(desc_frame, orient="vertical", command=self.description_text.yview)
        desc_scroll.pack(side="right", fill="y")
        self.description_text.config(yscrollcommand=desc_scroll.set)

        self.completed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(card, text="Задача выполнена", variable=self.completed_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="e")

        ttk.Button(buttons, text="Добавить", style="Accent.TButton", command=self.add_task).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Изменить", style="Accent.TButton", command=self.edit_task).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Удалить", command=self.delete_task).pack(side="left", padx=4)
        ttk.Button(buttons, text="Очистить форму", command=self.clear_form).pack(side="left", padx=4)

        card.columnconfigure(1, weight=1)
        card.rowconfigure(3, weight=1)

    def _create_trackers_panel(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(5, 0))

        ttk.Label(card, text="Трекеры", style="Header.TLabel").pack(anchor="w")

        notebook = ttk.Notebook(card)
        notebook.pack(fill="both", expand=True, pady=(8, 0))

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
        ttk.Label(tab, textvariable=text_var).pack(anchor="w")

        bar = ttk.Progressbar(tab, orient="horizontal", mode="determinate")
        bar.pack(fill="x", pady=(6, 10))

        row = ttk.Frame(tab)
        row.pack(fill="x")

        ttk.Button(row, text=f"−{cfg.step}", command=lambda: self._tracker_delta(key, -cfg.step)).pack(
            side="left"
        )
        ttk.Button(row, text=f"+{cfg.step}", command=lambda: self._tracker_delta(key, cfg.step)).pack(
            side="left", padx=(6, 12)
        )

        ttk.Label(row, text="Норма:").pack(side="left")

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
        spin.pack(side="left", padx=6)
        spin.bind("<Return>", lambda _e: self._apply_goal_counter(key))
        spin.bind("<FocusOut>", lambda _e: self._apply_goal_counter(key))

        ttk.Button(row, text="Сброс", command=lambda: self._reset_tracker(key)).pack(side="right")

        self.tracker_ui[key] = {"text": text_var, "bar": bar, "goal": goal_var}

    def _build_sleep_tab(self, tab: ttk.Frame, key: str) -> None:
        text_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=text_var).pack(anchor="w")

        bar = ttk.Progressbar(tab, orient="horizontal", mode="determinate")
        bar.pack(fill="x", pady=(6, 10))

        row1 = ttk.Frame(tab)
        row1.pack(fill="x")

        ttk.Label(row1, text="Сон (чч:мм):").pack(side="left")
        value_var = tk.StringVar(value=self.tracker_mgr.format_value(key))
        ttk.Entry(row1, width=8, textvariable=value_var).pack(side="left", padx=6)

        ttk.Button(row1, text="Установить", command=lambda: self._set_sleep_value(key)).pack(
            side="left"
        )

        ttk.Button(row1, text="+30м", command=lambda: self._tracker_delta(key, 30)).pack(
            side="left", padx=(10, 0)
        )
        ttk.Button(row1, text="−30м", command=lambda: self._tracker_delta(key, -30)).pack(
            side="left", padx=6
        )

        row2 = ttk.Frame(tab)
        row2.pack(fill="x", pady=(10, 0))

        ttk.Label(row2, text="Норма (чч:мм):").pack(side="left")
        goal_var = tk.StringVar(value=self.tracker_mgr.format_goal(key))
        ttk.Entry(row2, width=8, textvariable=goal_var).pack(side="left", padx=6)

        ttk.Button(row2, text="Применить", command=lambda: self._apply_sleep_goal(key)).pack(
            side="left"
        )
        ttk.Button(row2, text="Сброс", command=lambda: self._reset_tracker(key)).pack(side="right")

        self.tracker_ui[key] = {
            "text": text_var,
            "bar": bar,
            "value": value_var,
            "goal_hhmm": goal_var,
        }

    @staticmethod
    def _show_congrats(congrats: Optional[Tuple[str, str]]) -> None:
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

    def on_task_selected(self, _event: tk.Event) -> None:
        try:
            idx = self._selected_task_index()
            if idx is None:
                return
            task = self.tasks[idx]

            self.time_entry.delete(0, "end")
            self.time_entry.insert(0, task.time.strftime("%H:%M"))

            self.title_entry.delete(0, "end")
            self.title_entry.insert(0, task.title)

            self.description_text.delete("1.0", "end")
            self.description_text.insert("1.0", task.description)

            self.completed_var.set(task.completed)
            self.status_var.set("Задача загружена в форму.")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def add_task(self) -> None:
        try:
            t = self._parse_time_entry(self.time_entry.get())
            self._validate_not_past(t)

            title = self.title_entry.get().strip()
            if not title:
                raise ValueError("Название задачи не может быть пустым.")

            desc = self.description_text.get("1.0", "end").strip()
            completed = bool(self.completed_var.get())

            self.tasks.append(Task(time=t, title=title, description=desc, completed=completed))
            self.tasks.sort(key=lambda t: t.time)

            self._refresh_tasks_list()
            self._save_all()
            self.clear_form()
            self.status_var.set("Задача добавлена и сохранена.")
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc))
        except Exception as exc:
            messagebox.showerror("Неожиданная ошибка", str(exc))

    def edit_task(self) -> None:
        try:
            idx = self._selected_task_index()
            if idx is None:
                messagebox.showwarning("Нет выбора", "Сначала выберите задачу в списке.")
                return

            old = self.tasks[idx]
            t = self._parse_time_entry(self.time_entry.get())

            title = self.title_entry.get().strip()
            if not title:
                raise ValueError("Название задачи не может быть пустым.")

            # проверка «в прошлом» только если время поменяли
            if t != old.time:
                self._validate_not_past(t)

            old.time = t
            old.title = title
            old.description = self.description_text.get("1.0", "end").strip()
            old.completed = bool(self.completed_var.get())

            self.tasks.sort(key=lambda t: t.time)
            self._refresh_tasks_list()
            self._save_all()
            self.status_var.set("Задача изменена и сохранена.")
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc))
        except Exception as exc:
            messagebox.showerror("Неожиданная ошибка", str(exc))

    def delete_task(self) -> None:
        try:
            idx = self._selected_task_index()
            if idx is None:
                messagebox.showwarning("Нет выбора", "Сначала выберите задачу в списке.")
                return
            if not messagebox.askyesno("Подтверждение", "Удалить выбранную задачу?"):
                return

            del self.tasks[idx]
            self._refresh_tasks_list()
            self._save_all()
            self.clear_form()
            self.status_var.set("Задача удалена и сохранена.")
        except Exception as exc:
            messagebox.showerror("Неожиданная ошибка", str(exc))

    def clear_form(self) -> None:
        self.time_entry.delete(0, "end")
        self.title_entry.delete(0, "end")
        self.description_text.delete("1.0", "end")
        self.completed_var.set(False)
        self.status_var.set("Форма очищена.")

    @staticmethod
    def _parse_time_entry(time_str: str) -> dt.time:
        raw = time_str.strip()
        if not raw:
            raise ValueError("Поле времени не может быть пустым.")
        try:
            return parse_task_time(raw)
        except ValueError as exc:
            raise ValueError("Неверный формат времени. Используйте ЧЧ:ММ (например 09:30).") from exc

    def _validate_not_past(self, time_value: dt.time) -> None:
        task_dt = dt.datetime.combine(self.today, time_value)
        now = dt.datetime.now().replace(second=0, microsecond=0)
        if task_dt < now:
            raise ValueError("Нельзя поставить задачу на время в прошлом.")

    def _refresh_tasks_list(self) -> None:
        self.tasks_listbox.delete(0, "end")
        for task in self.tasks:
            self.tasks_listbox.insert("end", task.format_for_list())

    def _selected_task_index(self) -> Optional[int]:
        sel = self.tasks_listbox.curselection()
        if not sel:
            return None
        return int(sel[0])

    def _save_all(self) -> None:
        """Сохранить задачи + трекеры. Ошибка не должна закрыть приложение."""
        try:
            data = {
                "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
                "tasks": [t.to_dict() for t in self.tasks],
                "tracker_data": self.tracker_mgr.to_dict(),
            }
            tmp = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.storage_path)
        except OSError as exc:
            self.status_var.set("Ошибка сохранения.")
            messagebox.showwarning("Ошибка сохранения", f"Не удалось сохранить данные:\n{exc}")

    def _load_all(self) -> None:
        """Загрузить задачи + трекеры. При ошибке — не падаем."""
        if not self.storage_path.exists():
            self.status_var.set("Нет сохранённых данных (файл не найден).")
            return

        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))

            # tasks
            loaded_tasks: List[Task] = []
            skipped = 0
            for item in raw.get("tasks", []):
                try:
                    if not isinstance(item, dict):
                        raise ValueError
                    loaded_tasks.append(Task.from_dict(item))
                except (ValueError, TypeError):
                    skipped += 1
            self.tasks = sorted(loaded_tasks, key=lambda t: t.time)

            if skipped:
                messagebox.showwarning("Загрузка", f"Пропущено битых задач: {skipped}")

            # trackers
            tracker_data = raw.get("tracker_data", {})
            self.tracker_mgr.load_from_dict(tracker_data)

            self.status_var.set(f"Загружено задач: {len(self.tasks)}")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showwarning(
                "Не удалось загрузить данные",
                "Файл данных повреждён/недоступен.\n"
                "Приложение запущено с пустыми данными.\n\n"
                f"Подробности: {exc}",
            )
            self.tasks = []

    def change_window_size(self) -> None:
        try:
            width = simpledialog.askinteger(
                "Размер окна", "Ширина (px):", minvalue=600, maxvalue=1920, parent=self
            )
            if width is None:
                return
            height = simpledialog.askinteger(
                "Размер окна", "Высота (px):", minvalue=400, maxvalue=1080, parent=self
            )
            if height is None:
                return
            self.geometry(f"{width}x{height}")
            self.status_var.set(f"Размер окна: {width}x{height}")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def on_exit(self) -> None:
        if not messagebox.askokcancel("Выход", "Выйти из программы?"):
            return
        self._save_all()
        self.destroy()

    @staticmethod
    def show_about() -> None:
        messagebox.showinfo(
            "О программе",
            "Планировщик дня (Tkinter)\n"
            "• задачи + выполнено\n"
            "• трекеры: вода, шаги, сон, чтение\n"
            "• сохранение в JSON\n"
            "• похвала при достижении нормы",
        )


if __name__ == "__main__":
    DayPlannerApp().mainloop()