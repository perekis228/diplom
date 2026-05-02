import os
import sys
import json
from typing import Dict, Any

mixins_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(mixins_dir)
sys.path.append(src_dir)

from src.logger import log_to_file
# noinspection PyUnresolvedReferences


class FileManagerMixin:
    """Миксин для работы с файлами"""

    def __init__(self):
        super().__init__()

    def load_items_data(self, items_file: str, items_data: Dict[str, Dict[str, Any]]) -> None:
        """Загружает данные из json"""
        try:
            if not os.path.exists(items_file):
                self.append_to_console(f"Файл {items_file} не найден", "red")
                log_to_file(f"Файл {items_file} не найден", "WARNING")
                items_data.clear()
                return

            with open(items_file, 'r', encoding='utf-8') as file:
                loaded_data = json.load(file).get("items", {})

            if isinstance(loaded_data, dict):
                items_data.clear()
                items_data.update(loaded_data)
            else:
                self.append_to_console(f"Ошибка: ожидался словарь, получен {type(loaded_data)}", "red")
                log_to_file(f"Ошибка: ожидался словарь, получен {type(loaded_data)}", "ERROR")
                items_data.clear()
                return

            self.append_to_console(f"Загружено {len(items_data)} предметов из {items_file}", "green")
            log_to_file(f"Загружено {len(items_data)} предметов из {items_file}")

        except Exception as e:
            self.append_to_console(f"Ошибка при загрузке данных: {e}")
            log_to_file(f"Ошибка при загрузке данных: {e}", "ERROR")

    def _del_log(self) -> None:
        """Удаляет лог"""
        log_path = os.path.join(self.project_root, "logs", "tarkov_detector.log")
        if os.path.exists(log_path):
            try:
                os.remove(log_path)
            except Exception as e:
                self.append_to_console(f"Ошибка удаления лога", "orange")
                log_to_file(f"Ошибка удаления лога: {e}", "ERROR")
