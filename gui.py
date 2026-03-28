import sys
from PyQt5.QtWidgets import (QApplication,  # Главный класс
                             QMainWindow,   # Главное окно
                             QWidget,       # Базовый виджет для контейнера
                             QVBoxLayout,   # Вертикальный менеджер компоновки
                             QLabel,        # Текстовая метка
                             QPushButton)   # Кнопка
from PyQt5.QtCore import Qt                 # Содержит константы Qt
from PyQt5.QtGui import QFont               # Для настройки шрифтов


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_on = False
        self.init_ui()
        self.center()

    def init_ui(self):
        self.setWindowTitle("Детектор Tarkov")
        self.setGeometry(500, 500, 400, 300)

        # Центральный виджет и компоновка
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setAlignment(Qt.AlignCenter)

        # Заголовок
        title = QLabel("Детектор предметов")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(30)

        # Кнопка-переключатель
        self.toggle_button = QPushButton()
        self.toggle_button.setFont(QFont("Arial", 14, QFont.Bold))
        self.toggle_button.setFixedSize(200, 80)
        self.toggle_button.clicked.connect(self.toggle_status)
        layout.addWidget(self.toggle_button, alignment=Qt.AlignCenter)

        # Устанавливаем начальное состояние (выключен)
        self.update_ui()

    def update_ui(self):
        """Единый метод для обновления интерфейса"""
        if self.is_on:
            self.toggle_button.setText("ЗАПУЩЕН")
            self.toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 20px;
                    border: 2px solid #45a049;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            self.toggle_button.setText("ВЫКЛЮЧЕН")
            self.toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border-radius: 20px;
                    border: 2px solid #da190b;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
            """)

    def toggle_status(self):
        """Переключение статуса"""
        self.is_on = not self.is_on
        self.update_ui()  # Вызываем один метод для обновления

    def center(self):
        """Центрирует окно на экране"""
        # Получаем размеры экрана
        screen = QApplication.primaryScreen().geometry()
        # Получаем размеры окна
        window_geometry = self.frameGeometry()
        # Вычисляем центр экрана
        center_point = screen.center()
        # Перемещаем окно так, чтобы его центр совпал с центром экрана
        window_geometry.moveCenter(center_point)
        # Устанавливаем новую позицию
        self.move(window_geometry.topLeft())


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()