import os
import sys  # Для работы с аргументами командной строки и системными функциями
import json
from PyQt5.QtWidgets import (QApplication,  # Главный класс приложения
                             QWidget)  # Базовый виджет для контейнера
from PyQt5.QtCore import (Qt,  # Константы
                          QTimer,  # Для таймера автоскрытия
                          QRectF)  # Прямоугольник с вещественными координатами
from PyQt5.QtGui import (QPainter,  # Рисование
                         QPen,  # Стиль линий
                         QBrush,  # Заливка
                         QColor,  # Цвета
                         QFont,  # Шрифты
                         QFontMetrics)  # Размеры текста


class OverlayWindow(QWidget):
    """Класс прозрачного окна-оверлея для отображения рамок вокруг предметов"""
    def __init__(self):
        """Конструктор класса. Инициализирует окно и настраивает его свойства."""
        super().__init__()
        self.items = []  # Список предметов для отрисовки (JSON)
        self.init_ui()  # Вызываем метод инициализации интерфейса

    def init_ui(self):
        """Настройка прозрачного окна поверх всех окон"""
        # Устанавливаем флаги
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |  # Окно всегда поверх всех окон
            Qt.FramelessWindowHint |  # Убираем рамки и заголовок окна
            Qt.Tool |  # Окно не отображается в панели задач Windows
            Qt.WindowTransparentForInput  # Клики мыши проходят сквозь окно
        )

        # Делаем фон окна полностью прозрачным
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Получаем геометрию основного экрана
        screen = QApplication.primaryScreen().geometry()
        # Устанавливаем размер окна на весь экран
        self.setGeometry(screen)

        # Устанавливаем название окна
        self.setWindowTitle("Tarkov Item Overlay")

        # Создаем таймер для автоматического скрытия оверлея
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)  # Таймер сработает только один раз
        self.hide_timer.timeout.connect(self.hide)  # При срабатывании таймера скрываем окно

        # Показываем окно
        self.show()

    def update_items(self, items_data):
        """
        Обновляет список предметов для отрисовки и перерисовывает окно

        Аргументы:
            items_data: список словарей с данными о предметах
                        Каждый словарь содержит: 'class', 'bbox', 'price'
        """
        self.items = items_data
        self.hide_timer.stop()

        # Перерисовываем окно (вызывает метод paintEvent)
        self.update()

        # Запускаем таймер для автоматического скрытия через 8 секунд
        self.hide_timer.start(8000)

    def clear_items(self):
        """Очищает все предметы и перерисовывает окно"""
        self.items = []
        self.update()

    def paintEvent(self, event):
        """
        Обработчик события перерисовки окна.
        Вызывается автоматически при self.update() или когда окно нужно перерисовать.

        Аргументы:
            event: объект события (не используется в данном методе)
        """
        # Если нет предметов для отрисовки - выходим
        if not self.items:
            return

        # Создаем объект QPainter для рисования на окне
        painter = QPainter(self)
        # Включаем сглаживание (края линий и текст будут более гладкими)
        painter.setRenderHint(QPainter.Antialiasing)

        # Проходим по всем предметам и рисуем каждый
        for item in self.items:
            self.draw_item(painter, item)

    def draw_item(self, painter, item):
        """
        Рисует один предмет: рамку и цену

        Аргументы:
            painter: объект QPainter для рисования
            item: словарь с данными предмета (class, bbox, price)
        """
        # Извлекаем данные из словаря предмета
        class_name = item.get('class', 'Unknown')  # Название предмета
        price = item.get('price', 0)
        bbox = item.get('bbox', {})

        # Извлекаем координаты из bbox
        x1 = bbox.get('x1', 0)
        y1 = bbox.get('y1', 0)
        x2 = bbox.get('x2', 0)
        y2 = bbox.get('y2', 0)

        # Создаем прямоугольник QRectF(x, y, width, height)
        rect = QRectF(x1, y1, x2 - x1, y2 - y1)

        # ========== РИСУЕМ РАМКУ ВОКРУГ ПРЕДМЕТА ==========
        color = QColor(255, 0, 0)

        # Создаем перо
        pen = QPen(color, 3, Qt.SolidLine)  # Цвет, толщина 3 пикселя, сплошная линия
        painter.setPen(pen)  # Устанавливаем перо в painter
        painter.setBrush(Qt.NoBrush)  # Отключаем заливку

        # Рисуем прямоугольник
        painter.drawRect(rect)

        # ========== ФОРМИРУЕМ ТЕКСТ ДЛЯ ОТОБРАЖЕНИЯ ==========
        # Создаем текст в зависимости от наличия цены
        if price and price > 0:
            # Форматируем цену: добавляем пробелы между тысячами
            formatted_price = f"{price:,}".replace(",", " ")
            text = f"{formatted_price}₽"
        else:
            text = ""

        # ========== НАСТРАИВАЕМ ШРИФТ И ИЗМЕРЯЕМ ТЕКСТ ==========
        # Настраиваем шрифт для текста
        font = QFont("Arial", 11, QFont.Bold)
        painter.setFont(font)  # Устанавливаем шрифт в painter

        # Измеряем размер текста (ширина и высота в пикселях)
        font_metrics = QFontMetrics(font)
        text_rect = font_metrics.boundingRect(text)  # Прямоугольник, содержащий текст

        # ========== РАСЧЕТ ЦЕНТРИРОВАННОЙ ПОЗИЦИИ ТЕКСТА ==========
        # Вычисляем ширину рамки
        rect_width = x2 - x1

        # Центрируем текст по горизонтали (по центру рамки)
        text_x = x1 + (rect_width - text_rect.width()) / 2

        # Определяем позицию по вертикали (над рамкой или внутри)
        # По умолчанию - над рамкой
        text_y = y1 - 8

        # Проверяем, помещается ли текст над рамкой (не выходит за верх экрана)
        if text_y - text_rect.height() < 0:
            # Если не помещается, размещаем текст внутри рамки, по центру по вертикали
            rect_height = y2 - y1
            text_y = y1 + (rect_height - text_rect.height()) / 2

        # ========== РИСУЕМ ФОН ДЛЯ ТЕКСТА ==========
        # Создаем прямоугольник для фона под текстом (центрированный)
        bg_rect = QRectF(
            text_x - 5,  # X: левее текста на 5 пикселей
            text_y - text_rect.height() - 2,  # Y: выше текста на высоту шрифта
            text_rect.width() + 10,  # Ширина: ширина текста + 10 пикселей
            text_rect.height() + 4  # Высота: высота текста + 4 пикселя
        )

        # Рисуем полупрозрачный черный фон для текста (чтобы текст был читаемым)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.setPen(Qt.NoPen)  # Убираем обводку у фона
        painter.drawRoundedRect(bg_rect, 5, 5)  # Рисуем прямоугольник со скругленными углами (радиус 5)

        # ========== РИСУЕМ ТЕКСТ ==========
        # Устанавливаем цвет текста
        painter.setPen(QPen(color))
        # Рисуем текст в рассчитанных центрированных координатах
        painter.drawText(int(text_x), int(text_y), text)


def main():
    """Главная функция запуска оверлейного окна"""
    app = QApplication(sys.argv)
    overlay = OverlayWindow()

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        # Проверяем, является ли аргумент файлом .json
        if arg.endswith('.json') and os.path.exists(arg):
            try:
                with open(arg, 'r', encoding='utf-8') as f:
                    items_data = json.load(f)
                overlay.update_items(items_data)
                print(f"Оверлей загрузил {len(items_data)} предметов из файла {arg}")
            except Exception as e:
                print(f"Ошибка чтения файла: {e}")
        else:
            # Пробуем распарсить как JSON строку
            try:
                items_data = json.loads(arg)
                overlay.update_items(items_data)
                print(f"Оверлей загрузил {len(items_data)} предметов из строки")
            except json.JSONDecodeError as e:
                print(f"Ошибка: не удалось распарсить JSON данные: {e}")
    else:
        print("Ожидание данных...")

    sys.exit(app.exec_())


# Точка входа в программу
if __name__ == "__main__":
    main()