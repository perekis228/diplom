from ultralytics import YOLO
import os
import sys
import json
from typing import Dict, Any

DEFAULT_JSON_PATH = 'parse/tarkov_items.json'
DEFAULT_MODEL_PATH = 'best.pt'
DEFAULT_CONF_THRESHOLD = 0.7
DEFAULT_N_OUTPUT = 5


def load_items_data(json_path: str = DEFAULT_JSON_PATH) -> Dict[str, Dict[str, Any]]:
    """
    Загружает данные о предметах из JSON файла

    Args:
        json_path: путь к JSON файлу с предметами

    Returns:
        словарь {shortName: {name, price}}
    """

    if not os.path.exists(json_path):
        print(f"Файл {json_path} не найден! Цены не будут загружены", file=sys.stderr)
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'items' in data:
            items = data['items']
        else:
            items = data

        print(f"Загружено данных о {len(items)} предметах", file=sys.stderr)
        return items
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Ошибка загрузки: {e}", file=sys.stderr)
        return {}


def detect_items(
        image_path: str,
        model_path: str,
        items_data: Dict[str, Dict[str, Any]] = None,
        conf_threshold: float = DEFAULT_CONF_THRESHOLD
) -> list[Dict[str, Any]]:
    """
    Детекция предметов на изображении с добавлением информации о цене

    Args:
        image_path: путь к изображению
        model_path: путь к обученной модели
        items_data: словарь с данными о предметах (из tarkov_items.json)
        conf_threshold: порог уверенности (0-1)

    Returns:
        list: список найденных предметов с координатами и ценами
    """

    if not os.path.exists(image_path):
        print(f"Файл {image_path} не найден!", file=sys.stderr)
        return []

    if not os.path.exists(model_path):
        print(f"Модель {model_path} не найдена!", file=sys.stderr)
        return []

    print(f"Загрузка модели: {model_path}", file=sys.stderr)
    try:
        model = YOLO(model_path)
    except Exception as e:
        print(f"Ошибка загрузки модели: {e}", file=sys.stderr)
        return []

    print(f"Анализ изображения: {image_path}", file=sys.stderr)
    results = model(image_path, conf=conf_threshold, verbose=False)

    detected_items = []

    r = results[0]
    if r.boxes is None:
        print("Ничего не найдено", file=sys.stderr)
        return detected_items

    boxes = r.boxes
    print(f"Найдено предметов: {len(boxes)}", file=sys.stderr)

    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        class_id = int(box.cls[0])
        class_name = model.names[class_id]
        item_info_from_api = items_data.get(class_name, {})
        price_value = int(raw_price) if (raw_price := item_info_from_api.get('price')) is not None else None

        item_info = {
            'class': class_name,
            'bbox': {
                'x1': int(x1),
                'y1': int(y1),
                'x2': int(x2),
                'y2': int(y2)
            },
            'price': price_value
        }

        detected_items.append(item_info)

    detected_items.sort(key=lambda x: (x['price'] is None, x['price'] or float('inf')))
    return detected_items


def parse_args() -> tuple[str, int]:
    """
    Парсинг аргументов командной строки

    Returns:
        tuple: путь к скриншоту, количество выводимых предметов
    """
    if len(sys.argv) < 2:
        print("Ошибка: путь к скриншоту не передан", file=sys.stderr)
        print("Пример: python detection.py screenshot.png [количество]", file=sys.stderr)
        sys.exit(1)

    screenshot_path = sys.argv[1]
    n_output = DEFAULT_N_OUTPUT

    if len(sys.argv) >= 3:
        try:
            parsed = int(sys.argv[2])
            if parsed > 0:
                n_output = parsed
            else:
                print(f"Предупреждение: указано отрицательное или нулевое количество ({parsed}), "
                      f"установлено значение по умолчанию: {DEFAULT_N_OUTPUT}", file=sys.stderr)
        except ValueError:
            print(f"Предупреждение: '{sys.argv[2]}' не является числом, "
                  f"установлено значение по умолчанию: {DEFAULT_N_OUTPUT}", file=sys.stderr)

    print(f"Получен путь к скриншоту: {screenshot_path}", file=sys.stderr)
    print(f"Будет возвращено предметов: {n_output}", file=sys.stderr)

    return screenshot_path, n_output


def main():
    screenshot_path, n_output = parse_args()
    items_data = load_items_data()
    items = detect_items(screenshot_path, DEFAULT_MODEL_PATH, items_data, DEFAULT_CONF_THRESHOLD)

    if items is None:
        items = []

    output = items[:n_output]

    print(json.dumps(output))


if __name__ == "__main__":
    main()
