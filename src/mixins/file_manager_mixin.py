import os
import json
import traceback


class FileManagerMixin:
    """Миксин для работы с файлами"""

    def __init__(self):
        super().__init__()

    def load_items_data(self, items_file, items_data):
        """Загружает данные из json"""
        try:
            if not os.path.exists(items_file):
                self.append_to_console(f"Файл {items_file} не найден", "red")
                items_data.clear()
                return

            with open(items_file, 'r', encoding='utf-8') as file:
                loaded_data = json.load(file).get("items", {})

            if isinstance(loaded_data, dict):
                items_data.clear()
                items_data.update(loaded_data)
            else:
                self.append_to_console(f"Ошибка: ожидался словарь, получен {type(loaded_data)}", "red")
                items_data.clear()
                return

            self.append_to_console(f"Загружено {len(items_data)} предметов из {items_file}", "green")

        except Exception as e:
            print(f"Ошибка при загрузке данных: {e}")
            traceback.print_exc()

    def _del_log(self):
        log_path = os.path.join(self.project_root, "logs", "tarkov_detector.log")
        if os.path.exists(log_path):
            try:
                os.remove(log_path)
            except Exception as e:
                self.append_to_console(f"Ошибка удаления лога: {e}", "orange")