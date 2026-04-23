import json
import os
import sys
from typing import List, Dict, Any, Optional

from PyQt5.QtCore import Qt, QRectF, QTimer
from PyQt5.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from logger import log_both, log_to_file

sys.stdout.reconfigure(encoding='utf-8')


class OverlayWindow(QWidget):
    """Класс прозрачного окна-оверлея для отображения рамок вокруг предметов."""
    _overlay_font = QFont("Arial", 11, QFont.Bold)
    _overlay_font_metrics = QFontMetrics(_overlay_font)

    def __init__(self):
        """Инициализация окна наложения с прозрачным пользовательским интерфейсом и завершения проверки флага."""
        super().__init__()
        self.items = []
        self._init_ui()
        self._setup_exit_check()

    def _setup_exit_check(self) -> None:
        """Установка таймера для периодической проверки файла с флагом выхода."""
        self._exit_flag_timer = QTimer()
        self._exit_flag_timer.timeout.connect(self._check_exit_flag)  # type: ignore[arg-type]
        self._exit_flag_timer.start(200)

    def _check_exit_flag(self) -> None:
        """Проверяет наличие флага выхода из файла и закрывает окно, если он есть."""
        flag_path = os.path.join(os.getcwd(), "overlay_exit.flag")
        temp_detection_path = os.path.join(os.getcwd(), "temp_detection_result.json")
        if os.path.exists(flag_path):
            self._exit_flag_timer.stop()
            log_both("Обнаружен файл завершения, закрываю окно")
            try:
                os.remove(flag_path)
            except OSError as e:
                log_to_file(f"Ошибка удаления флага: {e}", "ERROR")

            if os.path.exists(temp_detection_path):
                try:
                    os.remove(temp_detection_path)
                except OSError as e:
                    log_to_file(f"Ошибка удаления temp файла: {e}", "ERROR")
            self.close()

    def _init_ui(self):
        """Настройка прозрачного окна поверх всех окон."""
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.geometry()
            self.setGeometry(geometry)
        self.setWindowTitle("Tarkov Item Overlay")
        self.show()

    def update_items(self, items_data: List[Dict[str, Any]]) -> None:
        """
        Обновляет список предметов для отрисовки и перерисовывает окно.

        Args:
            items_data: список словарей с данными о предметах, каждый словарь содержит:
                -'class' - название класса
                -'bbox' - словарь с координатами 'x1', 'y1', 'x2', 'y2'
                -'price' - цена в рублях
        """
        if items_data:
            self.items = items_data
            log_both(f"Загружено {len(items_data)} предметов")
            self.update()

    def paintEvent(self, _event):
        """
        Обработчик события перерисовки окна.
        Вызывается автоматически при self.update() или когда окно нужно перерисовать.

        Args:
            _event: объект события (не используется в данном методе)
        """
        if not self.items:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for item in self.items:
            try:
                self._draw_item(painter, item)
            except OSError as e:
                log_to_file(f"Ошибка отрисовки: {e}", "ERROR")

    @classmethod
    def _draw_item(cls, painter: QPainter, item: Dict[str, Any]) -> None:
        """
        Рисует один предмет: рамку и цену.

        Args:
            painter: объект QPainter для рисования
            item: словарь с данными предмета (class, bbox, price)
        """
        bbox = cls._normalize_bbox(item.get('bbox', {}))
        if not bbox:
            return

        cls._draw_bounding_box(painter, bbox)

        price = item.get('price')
        if price is not None and price >= 0:
            cls._draw_price_label(painter, price, bbox)

    @staticmethod
    def _normalize_bbox(bbox: Dict[str, float]) -> Optional[Dict[str, float]]:
        """
        Нормализует координаты bbox.

        Args:
            bbox: словарь с координатами

        Returns:
            Словарь с 'x', 'y', 'width', 'height' или None если координаты невалидны.
        """
        x1 = bbox.get('x1', 0)
        y1 = bbox.get('y1', 0)
        x2 = bbox.get('x2', 0)
        y2 = bbox.get('y2', 0)

        x, x2 = min(x1, x2), max(x1, x2)
        y, y2 = min(y1, y2), max(y1, y2)

        width = x2 - x
        height = y2 - y

        if width < 2 or height < 2:
            return None

        return {'x': x, 'y': y, 'width': width, 'height': height}

    @classmethod
    def _draw_bounding_box(
            cls,
            painter: QPainter,
            bbox: Dict[str, float]
    ) -> None:
        """
        Рисует красный прямоугольник вокруг предмета.

        Args:
            painter: объект QPainter для рисования
            bbox: словарь с координатами
        """
        rect = QRectF(bbox['x'], bbox['y'], bbox['width'], bbox['height'])
        color = QColor(255, 0, 0)
        pen = QPen(color, 3, Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

    @classmethod
    def _draw_price_label(
            cls,
            painter: QPainter,
            price: int,
            bbox: Dict[str, float]
    ) -> None:
        """
        Рисует ценник по центру над рамкой или внутри нее.

        Args:
            painter: объект QPainter для рисования
            price: цена в рублях
            bbox: словарь с координатами
        """
        text = f"{price:,}".replace(",", " ") + "₽"

        painter.setFont(cls._overlay_font)
        fm = cls._overlay_font_metrics

        text_width = fm.horizontalAdvance(text)
        text_x = bbox['x'] + (bbox['width'] - text_width) / 2

        ascent = fm.ascent()
        descent = fm.descent()
        text_height = ascent + descent

        if bbox['y'] >= text_height + 8:
            text_y = bbox['y'] - 8
        else:
            text_y = bbox['y'] + (bbox['height'] + ascent - descent) / 2

        cls._draw_text_background(painter, text_x, text_y, text_width, ascent, descent)

        color = QColor(255, 0, 0)
        painter.setPen(QPen(color))
        painter.drawText(int(text_x), int(text_y), text)

    @staticmethod
    def _draw_text_background(
            painter: QPainter,
            x: float,
            y: float,
            width: int,
            ascent: int,
            descent: int
    ) -> None:
        """
        Рисует полупрозрачный закругленный прямоугольник позади текста.

        Args:
            painter: объект QPainter для рисования
            x, y: координаты начала прямоугольника
            width: ширина прямоугольника
            ascent: высота от baseline до верхней границы текста
            descent: высота от baseline до нижней границы текста
        """
        padding_h = 5
        padding_v = 2

        bg_rect = QRectF(
            x - padding_h,
            y - ascent - padding_v,
            width + padding_h * 2,
            ascent + descent + padding_v * 2
        )

        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bg_rect, 5, 5)

    def closeEvent(self, event):
        """Обработчик события закрытия окна"""
        log_both("Оверлей закрывается")
        self._exit_flag_timer.stop()
        event.accept()
        QApplication.quit()


def main():
    """Главная функция запуска оверлейного окна"""

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    window = OverlayWindow()

    if len(sys.argv) > 1:
        file_path = sys.argv[1]

        if not os.path.exists(file_path):
            log_both(f"Файл не найден: {file_path}", "ERROR")
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    items = json.load(f)
                window.update_items(items)
                log_to_file(f"Данные загружены из {file_path}", "DEBUG")
            except json.JSONDecodeError as e:
                log_both(f"Невалидный JSON в {file_path}: {e}", "ERROR")
            except OSError as e:
                log_both(f"Не удалось прочитать файл {file_path}: {e}", "ERROR")

    exit_code = app.exec_()
    log_both(f"Оверлей остановлен (код: {exit_code})")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
