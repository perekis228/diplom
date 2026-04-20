import os
import sys
import json
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics

LOG_FILE = os.path.join(os.getcwd(), "tarkov_detector.log")


def log_to_file(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{level}] [OVERLAY] {msg}\n")
    except:
        pass


def log_to_console(msg):
    print(f"[Overlay] {msg}", flush=True)


def log_both(msg, level="INFO"):
    log_to_file(msg, level)
    log_to_console(msg)


class OverlayWindow(QWidget):
    """Класс прозрачного окна-оверлея для отображения рамок вокруг предметов"""
    def __init__(self):
        log_to_file("OverlayWindow.__init__ начат", "DEBUG")
        super().__init__()
        self.items = []
        self.init_ui()

        self.exit_flag_timer = QTimer()
        self.exit_flag_timer.timeout.connect(self.check_exit_flag)
        self.exit_flag_timer.start(200)

        log_to_file("OverlayWindow.__init__ завершён", "DEBUG")

    def check_exit_flag(self):
        flag_path = os.path.join(os.getcwd(), "overlay_exit.flag")
        if os.path.exists(flag_path):
            log_both("Обнаружен файл завершения, закрываю окно")
            try:
                os.remove(flag_path)
            except Exception as e:
                log_to_file(f"Ошибка удаления флага: {e}", "ERROR")
            self.exit_flag_timer.stop()
            self.close()

    def init_ui(self):
        """Настройка прозрачного окна поверх всех окон"""
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
            log_to_file(f"Геометрия: {geometry.width()}x{geometry.height()}", "DEBUG")
        self.setWindowTitle("Tarkov Item Overlay")
        self.show()
        log_to_file("init_ui завершён", "DEBUG")

    def update_items(self, items_data):
        """
        Обновляет список предметов для отрисовки и перерисовывает окно

        Аргументы:
            items_data: список словарей с данными о предметах
                        Каждый словарь содержит: 'class', 'bbox', 'price'
        """
        if items_data:
            self.items = items_data
            log_both(f"Загружено {len(items_data)} предметов")
            self.update()

    def paintEvent(self, event):
        """
        Обработчик события перерисовки окна.
        Вызывается автоматически при self.update() или когда окно нужно перерисовать.

        Аргументы:
            event: объект события (не используется в данном методе)
        """
        if not self.items:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for item in self.items:
            try:
                self.draw_item(painter, item)
            except Exception as e:
                log_to_file(f"Ошибка отрисовки: {e}", "ERROR")

    @staticmethod
    def draw_item(painter, item):
        """
        Рисует один предмет: рамку и цену

        Аргументы:
            painter: объект QPainter для рисования
            item: словарь с данными предмета (class, bbox, price)
        """
        try:
            price = item.get('price', 0)
            bbox = item.get('bbox', {})

            x1 = bbox.get('x1', 0)
            y1 = bbox.get('y1', 0)
            x2 = bbox.get('x2', 0)
            y2 = bbox.get('y2', 0)

            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)

            rect_width = x2 - x1
            rect_height = y2 - y1

            if rect_width < 2 or rect_height < 2:
                return

            rect = QRectF(x1, y1, rect_width, rect_height)
            color = QColor(255, 0, 0)
            pen = QPen(color, 3, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            if price and price >= 0:
                formatted_price = f"{int(price):,}".replace(",", " ")
                text = f"{formatted_price}₽"
                font = QFont("Arial", 11, QFont.Bold)
                painter.setFont(font)
                fm = QFontMetrics(font)
                text_width = fm.horizontalAdvance(text)
                ascent = fm.ascent()
                descent = fm.descent()
                text_x = x1 + (rect_width - text_width) / 2

                if y1 >= ascent + descent + 8:
                    text_y = y1 - 8
                else:
                    text_y = y1 + (rect_height + ascent - descent) / 2

                padding_h = 5
                padding_v = 2

                bg_rect = QRectF(
                    text_x - padding_h,
                    text_y - ascent - padding_v,
                    text_width + padding_h * 2,
                    ascent + descent + padding_v * 2
                )

                painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(bg_rect, 5, 5)
                painter.setPen(QPen(color))
                painter.drawText(int(text_x), int(text_y), text)
        except Exception as e:
            log_to_file(f"Ошибка в draw_item: {e}", "ERROR")

    def closeEvent(self, event):
        """Обработчик события закрытия окна"""
        log_both("Оверлей закрывается")
        self.exit_flag_timer.stop()
        event.accept()
        QApplication.quit()


def main():
    """Главная функция запуска оверлейного окна"""

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    window = OverlayWindow()

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                items = json.load(f)
            window.update_items(items)
            log_to_file(f"Данные загружены из {file_path}", "DEBUG")
        except Exception as e:
            log_both(f"Ошибка загрузки данных: {e}")

    log_to_file("Запуск app.exec_()", "DEBUG")
    exit_code = app.exec_()
    log_both(f"Оверлей остановлен (код: {exit_code})")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
