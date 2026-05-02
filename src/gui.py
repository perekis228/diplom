import sys
import os
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QTableWidget,
    QHeaderView,
    QSpinBox,
    QLineEdit,
)
from PyQt5.QtCore import (
    Qt,
    QProcess,
    QTimer,
)
from PyQt5.QtGui import QFont
from Switch import Switch

from mixins.console_mixin import ConsoleMixin
from mixins.detect_overlay_mixin import DetectOverlayMixin
from mixins.file_manager_mixin import FileManagerMixin
from mixins.hotkey_manager_mixin import HotkeyManagerMixin
from mixins.process_mixin import ProcessMixin
from mixins.table_mixin import TableMixin


sys.stdout.reconfigure(encoding='utf-8')  # type:ignore


class MainWindow(QMainWindow, ConsoleMixin, DetectOverlayMixin, FileManagerMixin,
                 HotkeyManagerMixin, ProcessMixin, TableMixin):
    def __init__(self):
        super().__init__()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.base_dir)
        self.main_script = os.path.abspath(sys.argv[0])
        for sub in ("temp", "data", "logs"):
            path = os.path.join(self.project_root, sub)
            os.makedirs(path, exist_ok=True)
        self.detector_is_on = False
        self.screenshot_path = None
        self.hotkey_handler = None
        self.all_items_data = {}
        self.favorite_items_data = {}
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.on_search_text_changed)
        self.current_search_text = ""
        self.n_items_for_detection = 5
        self.init_ui()
        self.center()
        self.init_hotkey_handler()
        flag_path = os.path.join(self.project_root, "temp", "overlay_exit.flag")

        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except:
                pass

    def init_ui(self):
        """Метод для создания пользовательского интерфейса"""
        self.setWindowTitle("Детектор Tarkov")
        self.setGeometry(0, 0, 1800, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        main_layout.addLayout(self._create_first_column(), 30)
        main_layout.addLayout(self._create_second_column(), 35)
        main_layout.addLayout(self._create_third_column(), 25)
        main_layout.addLayout(self._create_fourth_column(), 25)

        items_file = os.path.join(self.project_root, "data", "tarkov_items.json")
        self.load_items_data(items_file, self.all_items_data)

        self.update_ui()
        self._del_log()

    def _create_first_column(self):
        """Создаёт первую колонку (кнопки + консоль)"""
        layout = QVBoxLayout()

        layout.addLayout(self._create_top_panel())

        layout.addWidget(QLabel("Консоль вывода:"))
        layout.addWidget(self._create_console())

        return layout

    def _create_top_panel(self):
        """Создаёт панель с заголовком и кнопками управления"""
        layout = QVBoxLayout()

        title = QLabel("Детектор предметов")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(30)

        self.toggle_button = self._create_toggle_button()
        layout.addWidget(self.toggle_button, alignment=Qt.AlignCenter)
        layout.addSpacing(20)

        self.switch = Switch()
        self.switch.switchToggled.connect(self.on_switch_toggled)
        layout.addWidget(self.switch, alignment=Qt.AlignCenter)

        layout.addWidget(self._create_run_button())
        layout.addLayout(self._create_button_panel())

        return layout

    def _create_toggle_button(self):
        """Создаёт кнопку включения/выключения"""
        button = QPushButton()
        button.setFont(QFont("Arial", 14, QFont.Bold))
        button.setFixedSize(200, 80)
        button.clicked.connect(self.toggle_status)
        return button

    def _create_run_button(self):
        """Создаёт кнопку запуска детекции"""
        button = QPushButton("Начать/остановить детекцию и вывод в оверлее (Shift+L)")
        button.clicked.connect(self.take_screenshot_and_run)
        button.setEnabled(False)
        self.run_button = button
        return button

    def _create_button_panel(self):
        """Создаёт панель с дополнительными кнопками"""
        layout = QHBoxLayout()

        self.parse_button = QPushButton("Обновить цены")
        self.parse_button.clicked.connect(self.parse)
        layout.addWidget(self.parse_button)

        self.clear_button = QPushButton("Очистить консоль")
        self.clear_button.clicked.connect(self.clear_console)
        layout.addWidget(self.clear_button)

        return layout

    def _create_console(self):
        """Создаёт текстовое поле для консоли"""
        console = QTextEdit()
        console.setFont(QFont("Courier New", 10))
        console.setReadOnly(True)
        console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
            }
        """)
        self.console = console
        return console

    def _create_second_column(self):
        """Создаёт вторую колонку (ТОП предметов)"""
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Топ предметов:"))
        layout.addLayout(self._create_top_controls())
        layout.addSpacing(10)
        layout.addWidget(self._create_top_table())

        return layout

    def _create_top_controls(self):
        """Создаёт элементы управления для ТОП таблицы"""
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Количество выводимых предметов (1-20):"))

        self.number_spinbox = QSpinBox()
        self.number_spinbox.setRange(1, 20)
        self.number_spinbox.setValue(10)
        self.number_spinbox.setSingleStep(1)
        self.number_spinbox.setFixedWidth(80)
        layout.addWidget(self.number_spinbox)

        layout.addStretch()
        return layout

    def _create_top_table(self):
        """Создаёт таблицу для ТОП предметов"""
        table = QTableWidget()
        table.setFont(QFont("Arial", 10))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Предмет", "Цена"])
        table.setStyleSheet(self._get_table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)

        self.top_table = table
        return table

    def _create_third_column(self):
        """Создаёт третью колонку (поиск предметов)"""
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Поиск предметов:"))
        layout.addWidget(self._create_search_input())
        layout.addSpacing(10)

        self.search_results_label = QLabel("Найдено предметов: 0")
        self.search_results_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.search_results_label)
        layout.addSpacing(5)

        layout.addWidget(self._create_search_table())

        return layout

    def _create_search_input(self):
        """Создаёт поле ввода для поиска"""
        input_field = QLineEdit()
        input_field.setPlaceholderText("Введите название предмета...")
        input_field.setFont(QFont("Arial", 10))
        input_field.textChanged.connect(self.perform_search)
        input_field.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                padding: 8px;
            }
            QLineEdit:focus {
                border: 1px solid #4CAF50;
            }
        """)

        self.search_input = input_field
        return input_field

    def _create_search_table(self):
        """Создаёт таблицу для результатов поиска"""
        table = QTableWidget()
        table.setFont(QFont("Arial", 10))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["ShortName", "Name", "Price"])
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show_context_menu)
        table.setStyleSheet(self._get_table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)

        self.search_table = table
        return table

    def _create_fourth_column(self):
        """Создаёт четвёртую колонку (избранное)"""
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Избранное:"))

        del_button = QPushButton("Очистить избранное")
        del_button.clicked.connect(self.clear_favorite)
        layout.addWidget(del_button)

        layout.addWidget(self._create_favorite_table())

        favorite_file = os.path.join(self.project_root, "data", "favorite.json")
        self.load_items_data(favorite_file, self.favorite_items_data)
        self.update_favorite_table()

        return layout

    def _create_favorite_table(self):
        """Создаёт таблицу для избранного"""
        table = QTableWidget()
        table.setFont(QFont("Arial", 10))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["ShortName", "Name", "Price"])
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show_context_menu)
        table.setStyleSheet(self._get_table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)

        self.favorite_table = table
        return table

    @staticmethod
    def _get_table_style():
        """Возвращает общий стиль для таблиц"""
        return """
            QTableWidget {
                background-color: #2d2d2d;
                alternate-background-color: #3c3c3c;
                gridline-color: #555555;
                color: #d4d4d4;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #ffffff;
                padding: 8px;
                border: 1px solid #3c3c3c;
                font-weight: bold;
            }
        """

    def on_switch_toggled(self, checked):
        """Срабатывает при изменении состояния"""
        if checked:
            self.n_items_for_detection = 10
            self.append_to_console(f"Отображение 10 предметов")
        else:
            self.n_items_for_detection = 5
            self.append_to_console(f"Отображение 5 предметов")

    def parse(self):
        num_of_items = self.number_spinbox.value()

        def handle_stdout(text):
            self.append_to_console(text)

        def on_finished(exit_code, exit_status):
            if exit_status == QProcess.NormalExit and exit_code == 0:
                self.update_top_table()
                items_file = os.path.join(self.project_root, "data", "tarkov_items.json")
                self.load_items_data(items_file, self.all_items_data)

        self._start_script(
            script_name="parser.py",
            args=[str(num_of_items)],
            button=self.parse_button,
            stdout_handler=handle_stdout,
            finished_handler=on_finished
        )

    def update_ui(self):
        """Единый метод для обновления интерфейса"""
        if self.detector_is_on:
            self.toggle_button.setText("ЗАПУЩЕН")
            self.toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;  /* Зеленый фон */
                    color: white;               /* Белый текст */
                    border-radius: 20px;        /* Скругление углов */
                    border: 2px solid #45a049;  /* Темно-зеленая рамка */
                }
                QPushButton:hover {
                    background-color: #45a049;  /* При наведении - темнее */
                }
            """)
        else:
            self.toggle_button.setText("ВЫКЛЮЧЕН")
            self.toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;  /* Красный фон */
                    color: white;               /* Белый текст */
                    border-radius: 20px;        /* Скругление углов */
                    border: 2px solid #da190b;  /* Темно-красная рамка */
                }
                QPushButton:hover {
                    background-color: #d32f2f;  /* При наведении - темнее */
                }
            """)

    def toggle_status(self):
        """Переключение статуса"""
        self.detector_is_on = not self.detector_is_on
        self.update_ui()

        if self.detector_is_on:
            self.append_to_console("Детектор активирован", "green")
            if self.hotkey_handler.register_hotkey():
                self.append_to_console(
                    "Глобальная горячая клавиша Shift+L зарегистрирована (работает даже когда окно неактивно)", "green")
            else:
                self.append_to_console(
                    "Ошибка при регистрации горячей клавиши. Возможно, требуются права администратора", "orange")
            self.run_button.setEnabled(True)
        else:
            self.append_to_console("Детектор деактивирован", "yellow")
            self.hotkey_handler.unregister_hotkey()
            self.append_to_console("Глобальная горячая клавиша Shift+L отключена", "yellow")
            self.run_button.setEnabled(False)

    def center(self):
        """Центрирует окно на экране"""
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def closeEvent(self, event):
        """Закрытие главного окна"""
        self.append_to_console("Закрытие приложения...", "orange")

        for key, proc in self._processes.items():
            if proc.state() == QProcess.Running:
                proc.terminate()
                proc.waitForFinished(1000)

        if self.hotkey_handler:
            self.hotkey_handler.unregister_hotkey()

        temp_files = [
            os.path.join(self.project_root, "temp", "screenshot.png"),
            os.path.join(self.project_root, "temp", "temp_detection_result.json"),
            os.path.join(self.project_root, "temp", "overlay_exit.flag")
        ]

        for filepath in temp_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass

        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
