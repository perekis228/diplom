import requests
import json


def parse_tarkov_dev(query_txt):
    """Парсит все предметы из tarkov.dev GraphQL API"""
    # GraphQL запрос
    query = load_query(query_txt)

    url = "https://api.tarkov.dev/graphql"

    headers = {
        'Content-Type': 'application/json',  # Тип отправляемых данных
        'Accept': 'application/json',  # Тип ожидаемых данных
        'User-Agent': 'Mozilla/5.0 (Diploma Project)'
    }

    # Тело POST-запроса
    payload = {
        'query': query
    }

    print("Запрос данных из tarkov.dev.\n")

    # Запрос
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"Ошибка HTTP: {response.status_code}")
            print(response.text[:200])
            return None

        data = response.json()

        if 'errors' in data:
            print(f"GraphQL ошибка: {data['errors']}")
            return None

        tarkov_items = data.get('data', {}).get('items', [])

        print(f"Получено предметов: {len(tarkov_items)}\n")

        return tarkov_items

    except Exception as e:
        print(f"Ошибка во время запроса: {e}")
        return None


def load_query(filename):
    """Загружает GraphQL запрос из txt"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Файл {filename} не найден, возвращён стандартный запрос")
        with open("query_long.txt", 'r', encoding='utf-8') as f:
            return f.read().strip()


def save_items_to_json(tarkov_items, filename='tarkov_items.json'):
    """Сохраняет предметы в JSON файл"""
    mapping = {}

    for item in tarkov_items:
        if item['shortName']:
            short_name = item['shortName']
            mapping[short_name] = {
                'name': item['name'],
                'price': item['avg24hPrice']
            }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)  # indent - отступы

    print(f"Данные сохранены в {filename}\n")


# Запуск парсера
if __name__ == "__main__":

    items = parse_tarkov_dev("query_short.txt")

    if items:
        # Сохранение в json
        save_items_to_json(items)
