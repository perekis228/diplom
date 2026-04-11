import requests
import json
from typing import List, Dict, Optional, Any
from pathlib import Path
import traceback
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PARSER_DIR = Path(__file__).parent


class Parser:
    def __init__(self, query_file: str = "query_short.txt", timeout: int = 5):
        """
        Инициализация парсера

        Args:
            query_file: Путь к файлу с GraphQL запросом
            timeout: Таймаут для HTTP запроса в секундах
        """
        self.base_url = "https://api.tarkov.dev/graphql"
        self.query_file = PARSER_DIR / query_file
        self.timeout = timeout
        self.query = self._load_query()
        self.user_agent = "Mozilla/5.0 (Diploma Project)"

    def _load_query(self) -> str:
        """
        Загружает GraphQL запрос из файла

        Returns:
            Строка с GraphQL запросом
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

    def parse(self) -> Optional[List[Dict[str, Any]]]:
        """
        Выполняет запрос к API и возвращает список предметов

        Returns:
            Список предметов или None в случае ошибки
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

        try:
            test_response = requests.get("https://api.tarkov.dev", timeout=5)
            print(f"API доступен. Статус: {test_response.status_code}")
        except Exception as e:
            print(f"API недоступен: {e}")

        try:
            # Используем сессию для лучшей обработки соединения
            session = requests.Session()

            # Добавляем retry адаптер для повторных попыток
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)

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
                print(f"   {response.text[:200]}")
                return None

            data = response.json()

            if 'errors' in data:
                print(f"GraphQL ошибка: {data['errors']}")
                return None

            items = data.get('data', {}).get('items', [])
            print(f"Получено предметов: {len(items)}")

            return items

        except requests.exceptions.SSLError as e:
            print(f"SSL ошибка: {e}")
            print("Пробуем без проверки SSL...")
            try:
                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                    verify=False  # Отключаем проверку SSL
                )
                print(f"Статус (без SSL проверки): {response.status_code}")
                return response.json().get('data', {}).get('items', [])
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
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def to_json(items: List[Dict[str, Any]], filename: str = 'tarkov_items.json'):
        """
        Сохраняет предметы в JSON файл

        Args:
            items: Список предметов из API
            filename: Имя выходного файла
        """
        mapping = {}

        for item in items:
            short_name = item.get('shortName')
            if short_name:
                name = item.get('name', '')
                price = item.get('avg24hPrice', 0)
                if short_name == 'Tushonka' and 'Large' in name:
                    short_name += ' L'
                elif short_name == 'Tushonka' and 'Small' in name:
                    short_name += ' S'
                elif short_name == 'Pâté':
                    short_name = 'Pate'

                mapping[short_name] = {
                    'name': name,
                    'price': price
                }

        filename = PARSER_DIR / filename
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        print(f"Данные сохранены в {filename}")
        print(f"Всего предметов: {len(mapping)}")

    @staticmethod
    def to_json_top(items: List[Dict[str, Any]], count: int = 5, top_file: str = 'top.json'):
        items_with_price = [item for item in items if item.get('avg24hPrice') is not None]
        sorted_items = sorted(items_with_price, key=lambda x: x['avg24hPrice'], reverse=True)
        top = sorted_items[:count]
        result = [{'shortName': item['shortName'],
                   'avg24hPrice': item['avg24hPrice'],
                   'name': item['name']} for item in top]

        top_file = PARSER_DIR / top_file
        with open(top_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def run(self, output_file: str = 'tarkov_items.json', count: int = 5, top_file: str = 'top.json'):
        """
        Запускает полный цикл: парсинг -> сохранение в JSON

        Args:
            output_file: Имя выходного JSON файла
            count: Количество сохраняемых предметов
            top_file: Имя выходного топа JSON файла
        """
        print("=" * 20, "Parser Tarkov.dev", "=" * 20)
        print(f"Рабочая директория: {Path.cwd()}")
        print(f"Директория парсера: {PARSER_DIR}")
        print(f"Файл запроса: {self.query_file}")

        items = self.parse()

        if items:
            self.to_json(items, output_file)
            self.to_json_top(items, count, top_file)
            print("Парсинг успешно завершен!")
            return True
        else:
            print("Не удалось получить данные")
            return False


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            try:
                top_count = int(sys.argv[1])
                # Проверяем, что число в допустимом диапазоне
                if top_count < 1 or top_count > 20:
                    print(f"Предупреждение: количество предметов должно быть от 1 до 20. Установлено значение 5")
                    top_count = 5
            except ValueError:
                print(f"Предупреждение: неверный формат числа '{sys.argv[1]}'. Установлено значение 5")
                top_count = 5
        else:
            top_count = 5
            print(f"Количество предметов не указано. Используется значение по умолчанию: {top_count}")

        print(f"Запуск парсера для {top_count} предметов...")

        parser = Parser(query_file="query_short.txt", timeout=10)
        success = parser.run("tarkov_items.json", top_count, "top.json")
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)
