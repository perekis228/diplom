import os
import sys
from datetime import datetime

LOG_FILE = os.path.join(os.getcwd(), "tarkov_detector.log")


def _format_timestamp() -> str:
    """Возвращает timestamp в формате: YYYY-MM-DD HH:MM:SS.mmm"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def log_to_file(msg: str, level: str = "INFO") -> None:
    """
    Логгирует в файл tarkov_detector.log, если при записи произошла ошибка, выводит её в stderr

    Args:
        msg: текст лога
        level: уровень лога
    """
    timestamp = _format_timestamp()
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{level}] [OVERLAY] {msg}\n")
    except OSError:
        print(f"[{timestamp}] [{level}] [OVERLAY] {msg}", file=sys.stderr)


def log_to_console(msg: str) -> None:
    """
    Логгирует в stdout

    Args:
        msg: текст лога
    """
    print(f"[Overlay] {msg}", flush=True)


def log_both(msg: str, level: str = "INFO"):
    """
    Логгирует в файл tarkov_detector.log и в stdout

    Args:
        msg: текст лога
        level: уровень лога
    """
    log_to_file(msg, level)
    log_to_console(msg)
