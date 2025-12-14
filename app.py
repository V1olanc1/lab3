from __future__ import annotations
import datetime as dt
from pathlib import Path

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
