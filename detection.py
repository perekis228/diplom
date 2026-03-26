from ultralytics import YOLO
import os
import json
from typing import Optional, List, Dict, Any

def load_items_data(json_path: str = 'parse/tarkov_items.json') -> Dict[str, Dict[str, Any]]:
    """
    Загружает данные о предметах из JSON файла

    Args:
        json_path: путь к JSON файлу с предметами

    Returns:
        словарь {shortName: {name, price}}
    """
    if not os.path.exists(json_path):
        print(f"Файл {json_path} не найден! Цены не будут загружены")
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            items_data = json.load(f)
        print(f"Загружено данных о {len(items_data)} предметах")
        return items_data
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON: {e}")
        return {}
    except Exception as e:
        print(f"Ошибка загрузки: {e}")
        return {}


def detect_items(image_path: str, model_path: str, items_data: Dict[str, Dict[str, Any]] = None,
                 conf_threshold: float = 0.5) -> Optional[List[Dict[str, Any]]]:
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
        print(f"Файл {image_path} не найден!")
        return None

    if not os.path.exists(model_path):
        print(f"Модель {model_path} не найдена!")
        return None

    print(f"Загрузка модели: {model_path}")
    model = YOLO(model_path)

    print(f"Анализ изображения: {image_path}")
    results = model(image_path, conf=conf_threshold, verbose=False)

    detected_items = []

    for r in results:
        if r.boxes is None:
            print("Ничего не найдено")
            continue

        boxes = r.boxes
        print(f"Найдено предметов: {len(boxes)}")

        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            item_info_from_api = items_data.get(class_name, {})

            item_info = {
                'class': class_name,
                'bbox': {
                    'x1': int(x1),
                    'y1': int(y1),
                    'x2': int(x2),
                    'y2': int(y2)
                },
                'price': item_info_from_api.get('price')
            }

            detected_items.append(item_info)

        detected_items.sort(key=lambda x: (x['price'] is None, x['price'] if x['price'] is not None else float('inf')))
    return detected_items


if __name__ == "__main__":
    items_data = load_items_data('parse/tarkov_items.json')
    items = detect_items('test.png', 'best.pt', items_data, 0.7)

    if items:
        for item in items:
            print(item)
    else:
        print("Предметы не найдены или произошла ошибка")