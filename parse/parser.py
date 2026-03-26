import requests
import json
from typing import List, Dict, Optional, Any


class Parser:
    def __init__(self, query_file: str = "query_short.txt", timeout: int = 5):
        """
        Инициализация парсера

        Args:
            query_file: Путь к файлу с GraphQL запросом
            timeout: Таймаут для HTTP запроса в секундах
        """
        self.base_url = "https://api.tarkov.dev/graphql"
        self.query_file = query_file
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
            with open(self.query_file, 'r', encoding='utf-8') as f:
                return f.read().strip()

        except FileNotFoundError:
            print(f"Файл {self.query_file} не найден, использую query_long.txt")
            try:
                with open("query_long.txt", 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except FileNotFoundError:
                print("Не найден ни один файл с запросом!")
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
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

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

        except requests.exceptions.Timeout:
            print(f"Таймаут ({self.timeout} сек) при запросе к API")
            return None
        except requests.exceptions.ConnectionError:
            print("Ошибка подключения. Проверьте интернет-соединение")
            return None
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")
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

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        print(f"Данные сохранены в {filename}")
        print(f"Всего предметов: {len(mapping)}")

    def run(self, output_file: str = 'tarkov_items.json'):
        """
        Запускает полный цикл: парсинг -> сохранение в JSON

        Args:
            output_file: Имя выходного JSON файла
        """
        print("=" * 20, "Parser Tarkov.dev", "=" * 20)
        print(f"Файл запроса: {self.query_file}")

        items = self.parse()

        if items:
            self.to_json(items, output_file)
        else:
            print("Не удалось получить данные")


if __name__ == "__main__":
    parser = Parser(query_file="query_short.txt", timeout=10)
    parser.run("tarkov_items.json")
