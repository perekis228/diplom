import os
import sys
from datetime import datetime
import inspect

LOG_FILE = os.path.join(os.getcwd(), "../logs/tarkov_detector.log")


def _format_timestamp() -> str:
    """Возвращает timestamp в формате: YYYY-MM-DD HH:MM:SS.mmm"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _get_caller_filename() -> str:
    """Возвращает имя файла, из которого была вызвана функция логирования"""
    stack = inspect.stack()
    for frame_info in stack[1:]:
        filename = os.path.basename(frame_info.filename)
        if filename != "logger.py":
            return os.path.splitext(filename)[0].upper()
    return "UNKNOWN"


def log_to_file(msg: str, level: str = "INFO") -> None:
    """
    Логгирует в файл tarkov_detector.log, если при записи произошла ошибка, выводит её в stderr

    Args:
        msg: текст лога
        level: уровень лога
    """
    timestamp = _format_timestamp()
    tag = _get_caller_filename()
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{level}] [{tag}] {msg}\n")
    except OSError:
        print(f"[{timestamp}] [{level}] [{tag}] {msg}", file=sys.stderr)


def log_to_console(msg: str) -> None:
    """
    Логгирует в stdout

    Args:
        msg: текст лога
    """
    tag = _get_caller_filename()
    print(f"[{tag}] {msg}", flush=True)


def log_both(msg: str, level: str = "INFO"):
    """
    Логгирует в файл tarkov_detector.log и в stdout

    Args:
        msg: текст лога
        level: уровень лога
    """
    log_to_file(msg, level)
    log_to_console(msg)
