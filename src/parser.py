import json
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from logger import log_both, log_to_file, log_to_console

sys.stdout.reconfigure(encoding='utf-8')  # type: ignore

PARSER_DIR = Path(__file__).parent
DEFAULT_TIMEOUT = 30
DEFAULT_TOP_COUNT = 5
DEFAULT_CACHE_AGE_HOURS = 1
REQUEST_LIMIT = 1000
API_BASE_URL = "https://api.tarkov.dev/graphql"
USER_AGENT = "Mozilla/5.0 (Diploma Project)"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DEFAULT_OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "tarkov_items.json")
DEFAULT_TOP_FILE = os.path.join(PROJECT_ROOT, "data", "top.json")


class Parser:
    """
    Парсер для получения данных о предметах из API tarkov.dev.

    Выполняет GraphQL запрос, обрабатывает ответ и сохраняет
    результаты в JSON файлы:
        DEFAULT_OUTPUT_FILE: Все предметы
        DEFAULT_TOP_FILE: Топ N самых дорогих предметов
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        cache_max_age_hours: int = DEFAULT_CACHE_AGE_HOURS
    ) -> None:
        """
        Инициализация парсера.

        Args:
            timeout: Таймаут для HTTP запроса в секундах
            cache_max_age_hours: Максимальный возраст кэша в часах
        """
        self.base_url = API_BASE_URL
        self.timeout = timeout
        self.user_agent = USER_AGENT
        self.cache_max_age_hours = cache_max_age_hours

    def is_cache_expired(self, filename: str) -> bool:
        """
        Проверяет, нужно ли читать предметы из json

        Args:
            filename: Имя JSON файла

        Returns:
            bool: Нужно ли парсить
        """
        file_path = PARSER_DIR / filename

        if not file_path.exists():
            log_to_file(f"Файл кэша {filename} не найден", "DEBUG")
            return True

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = data.get('_metadata', {})
            timestamp = metadata.get('timestamp', 0)

            if timestamp == 0:
                log_to_file(f"Нет timestamp в кэше {filename}", "WARNING")
                return True

            last_updated = datetime.fromtimestamp(timestamp)
            age = datetime.now() - last_updated

            max_age = timedelta(hours=self.cache_max_age_hours)
            needs_update = age > max_age
            time_to_update = max_age - age

            if needs_update:
                log_both(f"Кэш устарел (возраст: {age})")
            else:
                log_both(f"Использую данные из кэша (возраст: {age})."
                         f"До обновления {str(time_to_update).split('.')[0]}.")
            return needs_update

        except Exception as e:
            log_to_file(f"Ошибка чтения кэша: {e}", "ERROR")
            return True

    @staticmethod
    def _read_json(filename: str) -> Optional[List[Dict[str, Any]]]:
        """
        Читает json

        Args:
            filename: Имя JSON файла

        Returns:
            Список предметов, пустой список если предметов нет
        """
        file_path = PARSER_DIR / filename

        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            items_dict = data.get('items', {})

            items_list = []
            for short_name, item_data in items_dict.items():
                items_list.append({
                    'shortName': short_name,
                    'name': item_data['name'],
                    'avg24hPrice': item_data['price']
                })

            log_to_file(f"Загружено предметов из кэша: {len(items_list)}", "DEBUG")
            return items_list
        except Exception as e:
            log_to_file(f"Ошибка чтения кэша: {e}", "ERROR")
            return []

    def _parse_paginated(self) -> Optional[List[Dict[str, Any]]]:
        """
        Загружает предметы постранично с лимитом limit,
        чтобы избежать таймаутов на большом ответе.
        """

        all_items = []
        offset = 0

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
        }

        while True:
            paginated_query = (
                "{"
                f"  items(limit: {REQUEST_LIMIT}, offset: {offset}) {{"
                "    name"
                "    shortName"
                "    avg24hPrice"
                "  }"
                "}"
            )
            payload = {'query': paginated_query}
            log_to_file(f"Запрос страницы offset={offset}, limit={REQUEST_LIMIT}", "DEBUG")

            try:
                resp = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                if resp.status_code != 200:
                    log_to_file(f"Ошибка HTTP {resp.status_code}: {resp.text[:200]}", "ERROR")
                    return None

                data = resp.json()
                if 'errors' in data:
                    log_to_file(f"GraphQL ошибка: {data['errors']}", "ERROR")
                    return None

                items_chunk = data['data']['items']
                if not items_chunk:
                    break

                all_items.extend(items_chunk)
                offset += REQUEST_LIMIT
                log_to_file(f"Получено +{len(items_chunk)} предметов (всего {len(all_items)})", "DEBUG")

            except Exception as e:
                log_to_file(f"Ошибка при получении страницы offset={offset}: {e}", "ERROR")
                return None

        log_both(f"Пагинация завершена: всего {len(all_items)} предметов")
        return all_items

    def parse(self) -> Optional[List[Dict[str, Any]]]:
        """
        Выполняет запрос к API и возвращает список предметов.

        Returns:
            Список предметов или None в случае ошибки.
        """

        try:
            items = self._parse_paginated()
            if items:
                log_both(f"Получено {len(items)} предметов (пагинация)")
                return items
        except Exception as e:
            log_to_file(f"Пагинация не удалась: {e}", "WARNING")

        return None

    @staticmethod
    def to_json(
        items: List[Dict[str, Any]],
        filename: str = DEFAULT_OUTPUT_FILE
    ) -> None:
        """
        Сохраняет предметы в JSON файл

        Args:
            items: Список предметов из API
            filename: Имя выходного файла
        """
        mapping = {}
        duplicate_count = 0

        for item in items:
            short_name = item.get('shortName')
            if not short_name:
                continue

            name = item.get('name', '')
            price = item.get('avg24hPrice', 0)

            if short_name == 'Tushonka':  # Одинаковые краткие наименования предметов
                if 'Large' in name:
                    short_name += ' L'
                elif 'Small' in name:
                    short_name += ' S'
            elif short_name == 'Pâté':  # ИИ обучается без диакритических символов
                short_name = 'Pate'

            mapping[short_name] = {
                'name': name,
                'price': price,
            }

            if short_name in mapping:
                duplicate_count += 1
                log_to_file(f"Duplicate item: {short_name} ({name})", "DEBUG")

        result = {
            '_metadata': {
                'timestamp': datetime.now().timestamp()
            },
            'items': mapping
        }

        file_path = PARSER_DIR / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        log_to_file(f"Сохранено {len(mapping)} предметов в {file_path} "
                    f"(дубликатов: {duplicate_count})", "INFO")
        log_to_console(f"Сохранено {len(mapping)} предметов")

    @staticmethod
    def to_json_top(
        items: List[Dict[str, Any]],
        count: int = DEFAULT_TOP_COUNT,
        top_file: str = DEFAULT_TOP_FILE
    ) -> None:
        """
        Сохраняет топ-N предметов по цене в JSON файл.

        Args:
            items: Список предметов из API.
            count: Количество предметов в топе.
            top_file: Имя выходного файла.
        """
        items_with_price = [
            item for item in items
            if item.get('avg24hPrice') is not None
        ]

        sorted_items = sorted(
            items_with_price,
            key=lambda x: x['avg24hPrice'],
            reverse=True
        )

        top = sorted_items[:count]

        result = {
            "items": {
                item['shortName']: {
                    'name': item['name'],
                    'avg24hPrice': item['avg24hPrice']
                }
                for item in top
            }
        }

        file_path = PARSER_DIR / top_file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        log_both(f"Топ-{len(top)} предметов сохранен в {top_file}")

    def run(
        self,
        output_file: str = DEFAULT_OUTPUT_FILE,
        count: int = DEFAULT_TOP_COUNT,
        top_file: str = DEFAULT_TOP_FILE
    ) -> bool:
        """
        Запускает полный цикл: парсинг -> сохранение в JSON.

        Args:
            output_file: Имя выходного JSON файла со всеми предметами.
            count: Количество сохраняемых предметов в top_file.
            top_file: Имя выходного JSON файла с топом предметов.
        """
        log_to_file(f"Рабочая директория: {Path.cwd()}", "DEBUG")
        log_to_file(f"Директория парсера: {PARSER_DIR}", "DEBUG")

        if self.is_cache_expired(output_file):
            items = self.parse()
            if items is None and (PARSER_DIR / output_file).exists():
                log_both("Ошибка получения свежих данных, использую кэш")
                items = self._read_json(output_file)
        else:
            items = self._read_json(output_file)

        if items:
            self.to_json(items, output_file)
            self.to_json_top(items, count, top_file)
            log_both("Парсинг успешно завершен!")
            return True
        else:
            log_to_file("Не удалось получить данные - нет предметов", "ERROR")
            log_to_console("Не удалось получить данные")
            return False


def main() -> None:
    """Точка входа для скрипта."""
    log_both("=" * 20 + "Parser Tarkov.dev" + "=" * 20)
    try:
        if len(sys.argv) > 1:
            try:
                top_count = int(sys.argv[1])
                if not 1 <= top_count <= 20:
                    raise ValueError(f"Количество должно быть от 1 до 20, получено {top_count}")
                log_to_file(f"Топ из agrs: {top_count}", "DEBUG")
            except ValueError as e:
                log_to_file(f"Предупреждение: {e}. Использую {DEFAULT_TOP_COUNT}", "WARNING")
                log_to_console(f"Предупреждение. Использую {DEFAULT_TOP_COUNT}")
                top_count = DEFAULT_TOP_COUNT
        else:
            top_count = DEFAULT_TOP_COUNT
            log_to_file(
                f"Количество предметов не указано."
                f"Используется значение по умолчанию: {top_count}",
                "DEBUG"
            )

        parser = Parser(timeout=DEFAULT_TIMEOUT)
        success = parser.run(DEFAULT_OUTPUT_FILE, top_count, DEFAULT_TOP_FILE)

        success = 0 if success else 1
        log_to_file(f"Парсер закончил работу с кодом: {success}")
        sys.exit(success)

    except Exception as e:
        log_to_file(f"Критическая ошибка: {e}", "ERROR")
        log_to_console("Критическая ошибка!")
        sys.exit(1)


if __name__ == "__main__":
    main()
