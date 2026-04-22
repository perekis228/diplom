from ultralytics import YOLO
import os
import sys
import json
import traceback
from typing import Dict, Any

from logger import log_both, log_to_file, log_to_console

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

    log_to_file(f"Загрузка предметов из {json_path}", "DEBUG")

    if not os.path.exists(json_path):
        log_to_file(f"Файл с ценами {json_path} не найден", "WARNING")
        log_to_console("⚠ Предупреждение: файл с ценами не найден")
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'items' in data:
            items = data['items']
        else:
            items = data

        log_both(f"Загружено данных о {len(items)} предметах")
        return items
    except json.JSONDecodeError as e:
        log_to_file(f"Ошибка парсинга JSON: {e}", "ERROR")
        log_to_console("Ошибка: файл с ценами поврежден")
        return {}
    except Exception as e:
        log_to_file(f"Ошибка загрузки: {e}", "ERROR")
        log_to_console(f"Ошибка загрузки цен")
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

    log_to_file(f"Старт детекции: image={image_path}, model={model_path}, conf={conf_threshold}", "INFO")

    if items_data is None:
        items_data = {}
        log_to_file("Данные о предметах не найдены, цены не будут доступны", "WARNING")

    if not os.path.exists(image_path):
        log_both(f"Файл {image_path} не найден!", "ERROR")
        return []

    if not os.path.exists(model_path):
        log_both(f"Модель {model_path} не найдена!", "ERROR")
        return []

    log_to_file(f"Загрузка модели: {model_path}")
    try:
        model = YOLO(model_path)
        log_to_file(f"Модель загружена ({len(model.names)} классов)")
    except Exception as e:
        log_to_file(f"Ошибка загрузки модели: {e}", "ERROR")
        log_to_console(f"Ошибка загрузки модели")
        return []

    print(f"Анализ изображения: {image_path}", file=sys.stderr)
    log_to_file(f"Анализ изображения {image_path} с уровнем уверенности {conf_threshold}", "INFO")
    log_to_console("Анализ изображения...")
    results = model(image_path, conf=conf_threshold, verbose=False)

    detected_items = []
    items_with_prices = 0

    r = results[0]
    if r.boxes is None:
        log_both("Анализ завершён, предметов не найдено", "WARNING")
        return detected_items

    boxes = r.boxes

    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        confidence = float(box.conf[0])
        class_id = int(box.cls[0])
        class_name = model.names[class_id]
        item_info_from_api = items_data.get(class_name, {})
        price_value = int(raw_price) if (raw_price := item_info_from_api.get('price')) is not None else None

        if price_value:
            items_with_prices += 1

        item_info = {
            'class': class_name,
            'bbox': {
                'x1': int(x1),
                'y1': int(y1),
                'x2': int(x2),
                'y2': int(y2)
            },
            'confidence': round(confidence, 3),
            'price': price_value
        }

        detected_items.append(item_info)
        log_to_file(f"  {class_name}: conf={confidence:.3f}, price={price_value}", "DEBUG")

    log_both(f"Найдено объектов с ценой/всего объектов: {items_with_prices}/{len(detected_items)}", "INFO")

    detected_items.sort(key=lambda x: (x['price'] is None, x['price'] or float('inf')))
    return detected_items


def parse_args() -> tuple[str, int]:
    """
    Парсинг аргументов командной строки

    Returns:
        tuple: путь к скриншоту, количество выводимых предметов
    """
    if len(sys.argv) < 2:
        log_both("Ошибка: путь к скриншоту не передан", "ERROR")
        log_to_console("Пример: python detection.py screenshot.png [количество]")
        sys.exit(1)

    screenshot_path = sys.argv[1]
    n_output = DEFAULT_N_OUTPUT

    if len(sys.argv) >= 3:
        try:
            parsed = int(sys.argv[2])
            if parsed > 0:
                n_output = parsed
                log_to_file(f"n_output установлен {n_output} из аргумента", "DEBUG")
            else:
                log_to_file(f"Предупреждение: указано отрицательное или нулевое количество ({parsed}), "
                            f"установлено значение по умолчанию: {DEFAULT_N_OUTPUT}", "WARNING")
        except ValueError:
            log_to_file(f"Предупреждение: '{sys.argv[2]}' не является числом, "
                        f"установлено значение по умолчанию: {DEFAULT_N_OUTPUT}", "WARNING")

    log_to_file(f"Получен путь к скриншоту: {screenshot_path}")
    log_to_file(f"Будет возвращено предметов: {n_output}")

    return screenshot_path, n_output


def main():
    """Точка входа для скрипта."""
    log_both("=" * 20 + "Detector Tarkov.dev" + "=" * 20)

    try:
        screenshot_path, n_output = parse_args()
        items_data = load_items_data()
        items = detect_items(
            screenshot_path,
            DEFAULT_MODEL_PATH,
            items_data,
            DEFAULT_CONF_THRESHOLD
        )

        if items is None:
            items = []

        output = items[:n_output]

        print(json.dumps(output, ensure_ascii=False))
        log_to_file(f"Вывод {len(output)} предметов (задано: {n_output})")

    except KeyboardInterrupt:
        log_both("Скрипт прерван пользователем", "WARNING")
        sys.exit(1)
    except Exception as e:
        log_to_file(f"Критическая ошибка: {e}\n{traceback.format_exc()}", "ERROR")
        log_to_console(f"Критическая ошибка")
        sys.exit(1)


if __name__ == "__main__":
    main()
