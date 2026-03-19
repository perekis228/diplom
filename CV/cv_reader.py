import cv2
import numpy as np
import os


def find_cells_gentle(image_path="EFT.png", x=65, y=65, tolerance=0.05, debug=True):
    # Загрузка изображения
    img_contours = cv2.imread(image_path)

    original = img_contours.copy()
    height, width = img_contours.shape[:2]
    print(f"Размер изображения: {width}x{height} пикселей")
    print(f"Размер ячейки: {x}x{y} пикселей")

    if debug:
        os.makedirs("debug_output", exist_ok=True)

    # В ЧБ
    gray = cv2.cvtColor(img_contours, cv2.COLOR_BGR2GRAY)

    # Увеличение контраста
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)

    if debug:
        cv2.imwrite("debug_output/01_white_black.png", enhanced)

    # Градиент Собеля для нахождения горизонталльных и вертикальных линий любой толщины
    sobelx = cv2.Sobel(enhanced, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(enhanced, cv2.CV_64F, 0, 1, ksize=3)

    # Комбинация градиентов
    gradient = np.sqrt(sobelx ** 2 + sobely ** 2)
    # Всё ниже 0 в 0, всё выше 255 в 255
    gradient = np.uint8(np.clip(gradient, 0, 255))

    if debug:
        cv2.imwrite("debug_output/02_gradient.png", gradient)

    # Пороговая обработка градиента (меньше порога приравниваем к 0)
    _, thresh = cv2.threshold(gradient, 55, 255, cv2.THRESH_BINARY)

    if debug:
        cv2.imwrite("debug_output/03_threshold.png", thresh)

    # Соединение обрывков
    kernel = np.ones((1, 5), np.uint8)  # Горизонтальное ядро
    horizontal = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)

    kernel = np.ones((5, 1), np.uint8)  # Вертикальное ядро
    vertical = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Выделение крестовин
    crosses = cv2.bitwise_and(horizontal, vertical)

    if debug:
        cv2.imwrite("debug_output/04_crosses.png", crosses)

    # Выделение горизонтальных линий
    horizontal_lines = cv2.morphologyEx(crosses, cv2.MORPH_OPEN, np.ones((1, 7), np.uint8))

    # Выделение вертикальных линий
    vertical_lines = cv2.morphologyEx(crosses, cv2.MORPH_OPEN, np.ones((7, 1), np.uint8))

    # Комбо
    lines_preserved = cv2.bitwise_or(horizontal_lines, vertical_lines)

    if debug:
        cv2.imwrite("debug_output/05_preserved.png", lines_preserved)


    # Поиск контуров
    contours, hierarchy = cv2.findContours(lines_preserved, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Функция для получения глубины контура
    def get_contour_depth(hierarchy, idx):
        depth = 0
        parent = hierarchy[0][idx][3]  # Берём индекс родителя
        while parent != -1:  # Пока есть родитель
            depth += 1
            parent = hierarchy[0][parent][3]
        return depth

    # Находим максимальную глубину
    depths = []
    max_depth = 0

    for i in range(len(contours)):
        depth = get_contour_depth(hierarchy, i)
        depths.append(depth)
        max_depth = max(max_depth, depth)

    print(f"Максимальная глубина дерева: {max_depth}")

    if max_depth >= 3:

        # Фильтруем контуры
        filtered = []
        for i, contour in enumerate(contours):
            if depths[i] <= max_depth - 3:
                filtered.append(contour)

        # Создаем и сохраняем изображение
        img_contours= np.zeros((height, width, 3), dtype=np.uint8)
        cv2.drawContours(img_contours, filtered, -1, (255, 255, 255), 3)

    if debug:
        cv2.imwrite("debug_output/06_N3_contours.png", img_contours)
    print(f"Найдено контуров: {len(contours)}")

    # Поиск ячеек
    cell_candidates = []

    for cnt in contours:
        x_cnt, y_cnt, w, h = cv2.boundingRect(cnt)

        # Проверяем размер - должен быть близок к cell_size
        if x * (1-tolerance) < w < x * (1+tolerance) and y * (1-tolerance) < h < y * (1+tolerance):
            cell_candidates.append((x_cnt, y_cnt, w, h))

    print(f"Кандидатов в ячейки: {len(cell_candidates)}")

    if debug:
        # Визуализируем кандидатов
        cand_img = original.copy()
        for x_cnt, y_cnt, w, h in cell_candidates:
            cv2.rectangle(cand_img, (x_cnt, y_cnt), (x_cnt + w, y_cnt + h), (0, 255, 0), 1)
        cv2.imwrite("debug_output/07_candidates.png", cand_img)


    return cell_candidates


if __name__ == "__main__":
    candidates_1_1 = find_cells_gentle("EFT.png", x=65 * 1, y=65 * 1, tolerance=0.05, debug=False)
    candidates_1_2 = find_cells_gentle("EFT.png", x=65 * 1, y=65 * 2, tolerance=0.05, debug=False)
    candidates_2_1 = find_cells_gentle("EFT.png", x=65 * 2, y=65 * 1, tolerance=0.05, debug=False)
    candidates_2_2 = find_cells_gentle("EFT.png", x=65 * 2, y=65 * 2, tolerance=0.05, debug=False)
    candidates_3_3 = find_cells_gentle("EFT.png", x=65 * 3, y=65 * 3, tolerance=0.05, debug=False)
    result_img = cv2.imread("EFT.png")
    # Задаем цвета для каждого набора
    colors = [
        (0, 255, 0),  # 0. Ярко-зеленый
        (255, 0, 0),  # 1. Ярко-синий
        (0, 0, 255),  # 2. Ярко-красный
        (255, 255, 0),  # 3. Голубой (циан)
        (255, 0, 255),  # 4. Пурпурный (маджента)
        (0, 255, 255),  # 5. Желтый
        (128, 0, 128),  # 6. Фиолетовый
        (255, 165, 0)  # 7. Оранжевый
    ]
    # Рисуем первый набор (зеленые)
    for x, y, w, h in candidates_1_1:
        cv2.rectangle(result_img, (x, y), (x + w, y + h), colors[0], 2)

    # Рисуем второй набор (синие)
    for x, y, w, h in candidates_1_2:
        cv2.rectangle(result_img, (x, y), (x + w, y + h), colors[1], 2)

    # Рисуем третий набор (красные)
    for x, y, w, h in candidates_2_1:
        cv2.rectangle(result_img, (x, y), (x + w, y + h), colors[2], 2)

    for x, y, w, h in candidates_2_2:
        cv2.rectangle(result_img, (x, y), (x + w, y + h), colors[3], 2)

    for x, y, w, h in candidates_3_3:
        cv2.rectangle(result_img, (x, y), (x + w, y + h), colors[4], 2)

    # Сохраняем результат
    cv2.imwrite("debug_output/all_candidates.png", result_img)