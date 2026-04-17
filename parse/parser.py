import json
import sys
import traceback
from pathlib import Path
from datetime import datetime, timedelta
import urllib3
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PARSER_DIR = Path(__file__).parent
DEFAULT_TIMEOUT = 10
DEFAULT_TOP_COUNT = 5
DEFAULT_CACHE_AGE_HOURS = 1
API_BASE_URL = "https://api.tarkov.dev/graphql"
USER_AGENT = "Mozilla/5.0 (Diploma Project)"
DEFAULT_OUTPUT_FILE = "tarkov_items.json"
DEFAULT_TOP_FILE = "top.json"


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
        query_file: str = "query_short.txt",
        timeout: int = DEFAULT_TIMEOUT,
        cache_max_age_hours: int = DEFAULT_CACHE_AGE_HOURS
    ) -> None:
        """
        Инициализация парсера.

        Args:
            query_file: Путь к файлу с GraphQL запросом
            timeout: Таймаут для HTTP запроса в секундах
            cache_max_age_hours: Максимальный возраст кэша в часах
        """
        self.base_url = API_BASE_URL
        self.query_file = PARSER_DIR / query_file
        self.timeout = timeout
        self.user_agent = USER_AGENT
        self.cache_max_age_hours = cache_max_age_hours
        self.query = self._load_query()

    def _load_query(self) -> str:
        """
        Загружает GraphQL запрос из файла

        Returns:
            Строка с GraphQL запросом. Пустая строка, если файл не найден.
        """
        try:
            if not self.query_file.exists():
                print(f"Файл {self.query_file} не найден")
                # Пробуем альтернативный путь
                alt_file = PARSER_DIR / "query_long.txt"
                if alt_file.exists():
                    print(f"Использую {alt_file}")
                    self.query_file = alt_file
                else:
                    print("Не найден ни один файл с запросом!")
                    return ""

            with open(self.query_file, 'r', encoding='utf-8') as f:
                query = f.read().strip()
                print(f"Запрос загружен из {self.query_file}")
                return query

        except Exception as e:
            print(f"Ошибка при загрузке запроса: {e}")
            return ""

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
            return True

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = data.get('_metadata', {})
            timestamp = metadata.get('timestamp', 0)

            if timestamp == 0:
                return True

            last_updated = datetime.fromtimestamp(timestamp)
            age = datetime.now() - last_updated

            max_age = timedelta(hours=self.cache_max_age_hours)
            needs_update = age > max_age
            time_to_update = max_age - age

            if needs_update:
                print(f"Кэш устарел (возраст: {age})")
            else:
                print(f"Использую данные из кэша (возраст: {age})."
                      f"До обновления {str(time_to_update).split('.')[0]}.")
            return needs_update

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Ошибка чтения кэша: {e}")
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

            print(f"Загружено предметов из кэша: {len(items_list)}")
            return items_list

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Ошибка чтения кэша: {e}")
            return []

    @staticmethod
    def _create_session() -> requests.Session:
        """Создает сессию requests с настроенными повторными попытками."""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        return session

    @staticmethod
    def _extract_items_from_response(response: requests.Response) -> Optional[List[Dict[str, Any]]]:
        """
        Извлекает список предметов из ответа API.

        Args:
            response: Объект ответа requests

        Returns:
            Список предметов, пустой список если предметов нет,
            или None в случае ошибки структуры ответа
        """
        try:
            data = response.json()
        except json.JSONDecodeError:
            print(f"Сервер вернул не JSON: {response.text[:200]}")
            return None

        if 'errors' in data:
            print(f"GraphQL ошибка: {data['errors']}")
            return None

        items = data.get('data', {}).get('items')

        if items is None:
            print("Ответ не содержит поле 'data.items'")
            print(f"Ключи ответа: {list(data.keys())}")
            return []

        if not isinstance(items, list):
            print(f"Ожидался список, получен {type(items)}")
            return []

        print(f"Получено предметов: {len(items)}")
        return items

    def parse(self) -> Optional[List[Dict[str, Any]]]:
        """
        Выполняет запрос к API и возвращает список предметов.

        Returns:
            Список предметов или None в случае ошибки.
        """
        if not self.query:
            print("Нет запроса для отправки")
            return None

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': self.user_agent
        }

        payload = {'query': self.query}

        print(f"Отправка запроса к {self.base_url}...")

        # Проверка доступности API
        try:
            test_response = requests.get(
                "https://api.tarkov.dev",
                timeout=self.timeout
            )
            print(f"API доступен. Статус: {test_response.status_code}")
        except Exception as e:
            print(f"API недоступен: {e}")

        # Основной запрос c SSL
        try:
            with self._create_session() as session:
                response = session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                    verify=True  # Проверяем SSL сертификат
                )

            print(f"Ответ получен. Статус: {response.status_code}")

            if response.status_code != 200:
                print(f"Ошибка HTTP: {response.status_code}")
                # Ограничиваем вывод тела ошибки
                print(f"   {response.text[:200]}")
                return None

            return self._extract_items_from_response(response)

        except requests.exceptions.SSLError as e:
            print(f"SSL ошибка: {e}")
            print("Пробуем без проверки SSL...")
            try:
                # Отключаем предупреждения безопасности только для этой отчаянной попытки
                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                    verify=False
                )
                print(f"Статус (без SSL проверки): {response.status_code}")
                return self._extract_items_from_response(response)
            except Exception as e2:
                print(f"Ошибка при повторной попытке: {e2}")
                return None

        except requests.exceptions.Timeout:
            print(f"Таймаут ({self.timeout} сек) при запросе к API")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"Ошибка подключения: {e}")
            return None
        except Exception as e:
            print(f"Неизвестная ошибка: {type(e).__name__}: {e}")
            traceback.print_exc()
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

        result = {
            '_metadata': {
                'timestamp': datetime.now().timestamp()
            },
            'items': mapping
        }

        file_path = PARSER_DIR / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"Данные сохранены в {file_path}")
        print(f"Всего предметов: {len(mapping)}")

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
        print("=" * 20, "Parser Tarkov.dev", "=" * 20)
        print(f"Рабочая директория: {Path.cwd()}")
        print(f"Директория парсера: {PARSER_DIR}")
        print(f"Файл запроса: {self.query_file}")

        if self.is_cache_expired(output_file):
            items = self.parse()
        else:
            items = self._read_json(output_file)

        if items:
            self.to_json(items, output_file)
            self.to_json_top(items, count, top_file)
            print("Парсинг успешно завершен!")
            return True
        else:
            print("Не удалось получить данные")
            return False


def main() -> None:
    """Точка входа для скрипта."""
    try:
        if len(sys.argv) > 1:
            try:
                top_count = int(sys.argv[1])
                if not 1 <= top_count <= 20:
                    raise ValueError(f"Количество должно быть от 1 до 20, получено {top_count}")
            except ValueError as e:
                print(f"Предупреждение: {e}. Использую {DEFAULT_TOP_COUNT}")
                top_count = DEFAULT_TOP_COUNT
        else:
            top_count = DEFAULT_TOP_COUNT
            print(
                f"Количество предметов не указано."
                f"Используется значение по умолчанию: {top_count}"
            )

        print(f"Запуск парсера для {top_count} предметов...")

        parser = Parser(query_file="query_short.txt", timeout=DEFAULT_TIMEOUT)
        success = parser.run(DEFAULT_OUTPUT_FILE, top_count, DEFAULT_TOP_FILE)
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
