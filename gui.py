import sys
from PyQt5.QtWidgets import (QApplication,  # Главный класс приложения
                             QMainWindow,  # Класс главного окна
                             QWidget,  # Базовый виджет для контейнера
                             QVBoxLayout,  # Вертикальный менеджер компоновки
                             QHBoxLayout,  # Горизонтальный менеджер компоновки
                             QLabel,  # Текстовая метка
                             QPushButton,  # Кнопка
                             QTextEdit,  # Текстовое поле для консоли
                             QTableWidget,  # Редактор таблиц
                             QTableWidgetItem,  # Редактор ячейки таблицы
                             QHeaderView,  # Редактор заголовка таблицы
                             QSpinBox)
from PyQt5.QtCore import (Qt,  # Константы
                          QProcess,  # Для запуска внешних программ
                          QObject,  # Для сигналов
                          pyqtSignal)  # Для создания сигналов
from PyQt5.QtGui import QFont  # Шрифты
import os
import keyboard  # Для глобальных горячих клавиш (работает даже когда окно неактивно)
import json
import traceback


# Создаем класс-посредник для обработки горячих клавиш в отдельном потоке
class HotkeyHandler(QObject):
    # Создаем сигнал, который будет испускаться при нажатии горячей клавиши
    hotkey_pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.hotkey_global = None  # Идентификатор глобальной горячей клавиши

    def register_hotkey(self):
        """Регистрирует глобальную горячую клавишу"""
        try:
            # Регистрируем горячую клавишу
            self.hotkey_global = keyboard.add_hotkey('shift+l', self._on_hotkey)
            return True
        except Exception as e:
            print(f"Ошибка регистрации горячей клавиши: {e}")
            return False

    def _on_hotkey(self):
        """Внутренний обработчик нажатия клавиши (вызывается из потока keyboard)"""
        # Испускаем сигнал вместо прямого вызова GUI методов
        self.hotkey_pressed.emit()

    def unregister_hotkey(self):
        """Отменяет регистрацию глобальной горячей клавиши"""
        if self.hotkey_global is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_global)
                self.hotkey_global = None
            except Exception as e:
                print(f"Ошибка отключения горячей клавиши: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_on = False  # Флаг состояния детектора (включен/выключен)
        self.detection_process = None  # Переменная для хранения объекта процесса detection.py
        self.overlay_process = None  # Переменная для хранения объекта процесса overlay.py
        self.parse_process = None  # Переменная для хранения объекта процесса parser.py
        self.screenshot_path = None  # Путь к последнему сделанному скриншоту
        self.hotkey_handler = None  # Обработчик горячих клавиш
        self.top_table = None  # Хранение предметов для ТОП таблицы
        # self.favorite_table = None  # Хранение предметов для таблицы избранного
        self.init_ui()  # Вызываем метод инициализации интерфейса
        self.center()  # Вызываем метод центрирования окна на экране
        self.init_hotkey_handler()  # Инициализируем обработчик горячих клавиш


    def init_hotkey_handler(self):
        """Инициализирует обработчик горячих клавиш"""
        self.hotkey_handler = HotkeyHandler()
        # Подключаем сигнал из потока keyboard к слоту в основном потоке GUI
        self.hotkey_handler.hotkey_pressed.connect(self.on_hotkey_activated)

    def init_ui(self):
        """Метод для создания пользовательского интерфейса"""
        self.setWindowTitle("Детектор Tarkov")
        self.setGeometry(0, 0, 1200, 800)\

        # Создаем центральный виджет (обязательный элемент для QMainWindow)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # ========== ГЛАВНЫЙ ГОРИЗОНТАЛЬНЫЙ LAYOUT (две колонки) ==========
        main_layout = QHBoxLayout(central_widget)

        # ========== ЛЕВАЯ КОЛОНКА (кнопки + консоль) ==========
        left_layout = QVBoxLayout()

        # ВЕРХНЯЯ ПАНЕЛЬ С КНОПКАМИ
        top_layout = QVBoxLayout()

        # Создаем заголовок
        title = QLabel("Детектор предметов")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title)
        top_layout.addSpacing(30)

        # Создаем кнопку-переключатель
        self.toggle_button = QPushButton()
        self.toggle_button.setFont(QFont("Arial", 14, QFont.Bold))
        self.toggle_button.setFixedSize(200, 80)
        self.toggle_button.clicked.connect(self.toggle_status)
        top_layout.addWidget(self.toggle_button, alignment=Qt.AlignCenter)
        top_layout.addSpacing(20)

        # Создаем горизонтальный layout для группы кнопок управления
        button_layout = QHBoxLayout()

        # Кнопка создания скриншота и запуска detection.py
        self.run_button = QPushButton("Сделать скриншот и запустить detection.py (Shift+L)")
        self.run_button.clicked.connect(self.take_screenshot_and_run)
        button_layout.addWidget(self.run_button)
        self.run_button.setEnabled(False)

        # Кнопка запуска parser.py
        self.parse_button = QPushButton("Обновить цены")
        self.parse_button.clicked.connect(self.parse)
        button_layout.addWidget(self.parse_button)

        # Кнопка очистки консоли
        self.clear_button = QPushButton("Очистить консоль")
        self.clear_button.clicked.connect(self.clear_console)
        button_layout.addWidget(self.clear_button)

        top_layout.addLayout(button_layout)

        left_layout.addLayout(top_layout)

        # ========== КОНСОЛЬ ДЛЯ ВЫВОДА ==========
        console_label = QLabel("Консоль вывода:")
        console_label.setFont(QFont("Arial", 10, QFont.Bold))
        left_layout.addWidget(console_label)

        # Создаем текстовое поле для консоли
        self.console = QTextEdit()
        self.console.setFont(QFont("Courier New", 10))
        self.console.setReadOnly(True)

        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
            }
        """)
        left_layout.addWidget(self.console)

        # Добавляем левую колонку в главный layout (занимает 60% ширины)
        main_layout.addLayout(left_layout, 60)  # Stretch factor = 60

        # ========== ПРАВАЯ КОЛОНКА ==========
        right_layout = QVBoxLayout()

        table_label = QLabel("Топ предметов:")
        table_label.setFont(QFont("Arial", 10, QFont.Bold))
        right_layout.addWidget(table_label)

        # Создаем спинбокс для выбора числа от 1 до 20
        self.number_spinbox = QSpinBox()
        self.number_spinbox.setRange(1, 20)  # Диапазон [1, 20]
        self.number_spinbox.setValue(10)  # Начальное значение
        self.number_spinbox.setSingleStep(1)  # Шаг изменения
        self.number_spinbox.setFixedWidth(80)

        # Создаем горизонтальный layout для поля и кнопки
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Количество выводимых предметов (1-20):"))
        custom_layout.addWidget(self.number_spinbox)
        custom_layout.addStretch()  # Растягивает пустое пространство справа
        right_layout.addLayout(custom_layout)
        right_layout.addSpacing(10)

        # Создаем таблицу
        self.top_table = QTableWidget()
        self.top_table.setFont(QFont("Arial", 10))
        self.top_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.top_table.setColumnCount(2)
        self.top_table.setHorizontalHeaderLabels(["Предмет", "Цена"])

        # Настройка внешнего вида таблицы
        self.top_table.setStyleSheet("""
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
        """)

        # Растягиваем колонки
        self.top_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.top_table.setAlternatingRowColors(True)

        right_layout.addWidget(self.top_table)

        # Добавляем правую колонку в главный layout (занимает 40% ширины)
        main_layout.addLayout(right_layout, 40)  # Stretch factor = 40

        # Устанавливаем начальное состояние кнопки-переключателя
        self.update_ui()

    def on_hotkey_activated(self):
        """Обработчик активации горячей клавиши Shift+L (вызывается в основном потоке GUI)"""
        self.append_to_console("Горячая клавиша Shift+L нажата", "cyan")
        if self.is_on:
            if self.overlay_process and self.overlay_process.state() == QProcess.Running:
                self.stop_overlay()
            else:
                self.take_screenshot_and_run()
        else:
            self.append_to_console("Детектор выключен. Сначала включите детектор кнопкой 'ЗАПУЩЕН/ВЫКЛЮЧЕН'", "orange")

    def stop_overlay(self):
        """Останавливает оверлей"""
        if self.overlay_process and self.overlay_process.state() == QProcess.Running:
            self.append_to_console("Остановка оверлея...", "orange")

            self.overlay_process.terminate()
            if self.overlay_process.waitForFinished(1000):
                self.append_to_console("Оверлей успешно остановлен", "green")
            else:
                self.append_to_console("Оверлей не отвечает, принудительное завершение", "red")
                self.overlay_process.kill()
                self.overlay_process.waitForFinished(1000)

            self.overlay_process = None
            self.append_to_console("Оверлей остановлен", "yellow")

    def parse(self):
        """Запускает parser.py"""
        try:
            if self.parse_process and self.parse_process.state() == QProcess.Running:
                self.append_to_console("Процесс уже запущен!", "orange")
                return

            self.parse_process = QProcess()
            # Устанавливаем рабочую директорию
            self.parse_process.setWorkingDirectory(os.path.dirname(os.path.abspath(__file__)))
            # Объединяем stdout (стандартный вывод) и stderr (ошибки) в один поток
            self.parse_process.setProcessChannelMode(QProcess.MergedChannels)

            # ========== ПОДКЛЮЧАЕМ СИГНАЛЫ ПРОЦЕССА ==========
            # Сигнал readyReadStandardOutput - когда есть данные в stdout
            self.parse_process.readyReadStandardOutput.connect(self.handle_stdout_parse)
            # Сигнал readyReadStandardError - когда есть данные в stderr
            self.parse_process.readyReadStandardError.connect(self.handle_stderr_parse)
            # Сигнал finished - когда процесс завершился
            self.parse_process.finished.connect(self.process_finished_parse)
            # Сигнал started - когда процесс успешно запустился
            self.parse_process.started.connect(self.process_started_parse)
            # Обработка ошибок процесса
            self.parse_process.errorOccurred.connect(self.process_error_parse)

            # Получаем число из спинбокса
            num_of_items = self.number_spinbox.value()

            # Запускаем parser.py
            # sys.executable - путь к текущему интерпретатору Python
            parser_path = os.path.join("parse", "parser.py")
            if not os.path.exists(parser_path):
                self.append_to_console(f"Ошибка: файл {parser_path} не найден", "red")
                return
            self.parse_process.start(sys.executable, [parser_path, str(num_of_items)])

            # Ждем запуска процесса максимум 3 секунды
            if not self.parse_process.waitForStarted(3000):
                self.append_to_console("Ошибка: не удалось запустить процесс", "red")
                return

            self.parse_button.setEnabled(False)
        except Exception as e:  # Ловим любые исключения
            self.append_to_console(f"Ошибка при запуске parser.py: {e}", "red")

    def process_error_parse(self, error):
        """Обработчик ошибок процесса"""
        error_messages = {
            QProcess.FailedToStart: "Не удалось запустить процесс",
            QProcess.Crashed: "Процесс упал",
            QProcess.Timedout: "Таймаут процесса",
            QProcess.WriteError: "Ошибка записи",
            QProcess.ReadError: "Ошибка чтения",
            QProcess.UnknownError: "Неизвестная ошибка"
        }
        error_msg = error_messages.get(error, f"Ошибка {error}")
        self.append_to_console(f"Ошибка процесса parser.py: {error_msg}", "red")
        self.parse_button.setEnabled(True)

    def process_started_parse(self):
        """Обработчик запуска процесса"""
        self.append_to_console("parser.py успешно запущен!", "green")

    def process_finished_parse(self, exit_code, exit_status):
        """Обработчик завершения процесса"""
        # exit_code - код возврата (0 обычно означает успех)
        # exit_status - как завершился (NormalExit или CrashExit)
        if exit_status == QProcess.NormalExit:
            self.append_to_console(f"parser.py завершил работу с кодом {exit_code}", "yellow")
            # Если успешный парсинг, то обновляем таблицу
            if exit_code == 0:
                self.table_update()
        else:  # Если аварийное завершение
            self.append_to_console(f"parser.py был аварийно завершен", "red")

        self.parse_button.setEnabled(True)  # Разблокируем кнопку запуска

    def take_screenshot_and_run(self):
        """Делает скриншот всего экрана и запускает detection.py с путем к скриншоту"""
        try:
            # Получаем основной экран
            screen = QApplication.primaryScreen()
            if not screen:
                self.append_to_console("Ошибка: не удалось получить доступ к экрану", "red")
                return
            filename = "screenshot.png"
            self.screenshot_path = os.path.join(os.getcwd(), filename)  # Полный путь

            # Делаем скриншот всего экрана
            screenshot = screen.grabWindow(0)  # 0 - идентификатор корневого окна (весь экран)

            # Сохраняем скриншот
            success = screenshot.save(self.screenshot_path, "PNG")

            if success:
                self.append_to_console(f"Скриншот сохранен: {self.screenshot_path}", "green")
                # Запускаем detection.py с путем к скриншоту
                self.run_detect_with_screenshot()
            else:
                self.append_to_console("Ошибка: не удалось сохранить скриншот", "red")

        except Exception as e:  # Ловим любые исключения
            self.append_to_console(f"Ошибка при создании скриншота: {e}", "red")

    def run_detect_with_screenshot(self):
        """Запускает detection.py с передачей пути к скриншоту в качестве аргумента"""
        try:
            # Проверяем, не запущен ли уже процесс
            if self.detection_process and self.detection_process.state() == QProcess.Running:
                self.append_to_console("Процесс уже запущен!", "orange")
                return

            # Проверяем, существует ли файл скриншота
            if not self.screenshot_path or not os.path.exists(self.screenshot_path):
                self.append_to_console(f"Ошибка: файл скриншота не найден: {self.screenshot_path}", "red")
                return

            # Создаем новый объект QProcess (управляет внешним процессом)
            self.detection_process = QProcess()
            # Объединяем stdout (стандартный вывод) и stderr (ошибки) в один поток
            self.detection_process.setProcessChannelMode(QProcess.MergedChannels)

            # ========== ПОДКЛЮЧАЕМ СИГНАЛЫ ПРОЦЕССА ==========
            # Сигнал readyReadStandardOutput - когда есть данные в stdout
            self.detection_process.readyReadStandardOutput.connect(self.handle_stdout_detection)
            # Сигнал readyReadStandardError - когда есть данные в stderr
            self.detection_process.readyReadStandardError.connect(self.handle_stderr_detection)
            # Сигнал finished - когда процесс завершился
            self.detection_process.finished.connect(self.process_finished_detection)
            # Сигнал started - когда процесс успешно запустился
            self.detection_process.started.connect(self.process_started_detection)

            # Запускаем detection.py и передаем путь к скриншоту как аргумент командной строки
            # sys.executable - путь к текущему интерпретатору Python
            self.detection_process.start(sys.executable, ["detection.py", self.screenshot_path])

            # Ждем запуска процесса максимум 3 секунды
            if not self.detection_process.waitForStarted(3000):
                self.append_to_console("Ошибка: не удалось запустить процесс", "red")
                return

            self.run_button.setEnabled(False)  # Блокируем кнопку запуска

        except Exception as e:  # Ловим любые исключения
            self.append_to_console(f"Ошибка при запуске: {e}", "red")

    def append_to_console(self, text, color=None):
        """Добавляет текст в консоль с опциональным цветом"""
        if color:
            # Формируем HTML-строку с цветом текста
            colored_text = f'<font color="{color}">{text}</font>'
            self.console.append(colored_text)
        else:
            self.console.append(text)

        # Автоматическая прокрутка вниз при добавлении нового текста
        scrollbar = self.console.verticalScrollBar()  # Получаем вертикальный скроллбар консоли
        scrollbar.setValue(scrollbar.maximum())  # Устанавливаем позицию скролла на максимум (вниз)

    def clear_console(self):
        """Очищает консоль"""
        self.console.clear()

    def handle_stdout_detection(self):
        """Обработка стандартного вывода с парсингом JSON"""
        if self.detection_process:
            # Читаем все данные из стандартного вывода
            data = self.detection_process.readAllStandardOutput()  # QByteArray
            # Декодируем байты в строку UTF-8, заменяем ошибки
            text = bytes(data).decode('utf-8', errors='replace').strip()

            if text.strip():
                try:
                    # Пробуем преобразовать текст в JSON
                    items_data = json.loads(text.strip())
                    self.process_detection_result(items_data)
                except json.JSONDecodeError:
                    self.append_to_console(text.strip())

    def handle_stderr_detection(self):
        """Обработка стандартного вывода ошибок"""
        if self.detection_process:
            # Читаем все данные из потока ошибок
            data = self.detection_process.readAllStandardError()
            # Декодируем байты в строку
            text = bytes(data).decode('utf-8', errors='replace').strip()
            if text:
                self.append_to_console(f"[ОШИБКА] {text}", "red")

    def handle_stdout_parse(self):
        """Обработка стандартного вывода с парсингом JSON"""
        if self.parse_process:
            try:
                # Читаем все данные из стандартного вывода
                data = self.parse_process.readAllStandardOutput()  # QByteArray
                # Декодируем байты в строку UTF-8, заменяем ошибки
                text = bytes(data).decode('utf-8', errors='replace').strip()
                if text:
                    self.append_to_console(text)
            except Exception as e:
                self.append_to_console(f"Ошибка при чтении вывода: {e}", "red")

    def handle_stderr_parse(self):
        """Обработка стандартного вывода ошибок"""
        if self.parse_process:
            # Читаем все данные из потока ошибок
            data = self.parse_process.readAllStandardError()
            # Декодируем байты в строку
            text = bytes(data).decode('utf-8', errors='replace').strip()
            if text:
                self.append_to_console(f"[ОШИБКА] {text}", "red")

    def process_started_detection(self):
        """Обработчик запуска процесса"""
        self.append_to_console("detection.py успешно запущен!", "green")

    def process_finished_detection(self, exit_code, exit_status):
        """Обработчик завершения процесса"""
        # exit_code - код возврата (0 обычно означает успех)
        # exit_status - как завершился (NormalExit или CrashExit)

        if exit_status == QProcess.NormalExit:
            self.append_to_console(f"detection.py завершил работу с кодом {exit_code}", "yellow")
        else:  # Если аварийное завершение
            self.append_to_console(f"detection.py был аварийно завершен", "red")

        self.run_button.setEnabled(True)  # Разблокируем кнопку запуска

    def update_ui(self):
        """Единый метод для обновления интерфейса"""
        if self.is_on:
            self.toggle_button.setText("ЗАПУЩЕН")
            # Устанавливаем зеленый стиль
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
            # Устанавливаем красный стиль
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
        # Переключаем флаг состояния
        self.is_on = not self.is_on
        self.update_ui()

        if self.is_on:
            self.append_to_console("Детектор активирован", "green")
            # Регистрируем глобальную горячую клавишу при активации
            if self.hotkey_handler.register_hotkey():
                self.append_to_console(
                    "Глобальная горячая клавиша Shift+L зарегистрирована (работает даже когда окно неактивно)", "green")
            else:
                self.append_to_console(
                    "Ошибка при регистрации горячей клавиши. Возможно, требуются права администратора", "orange")
            self.run_button.setEnabled(True)
        else:
            self.append_to_console("Детектор деактивирован", "yellow")
            # Отменяем регистрацию горячей клавиши при деактивации
            self.hotkey_handler.unregister_hotkey()
            self.append_to_console("Глобальная горячая клавиша Shift+L отключена", "yellow")
            self.run_button.setEnabled(False)

    def center(self):
        """Центрирует окно на экране"""
        # Получаем размеры экрана (геометрию первичного монитора)
        screen = QApplication.primaryScreen().geometry()
        # Получаем размеры нашего окна
        window_geometry = self.frameGeometry()
        # Вычисляем центр экрана
        center_point = screen.center()
        # Перемещаем окно так, чтобы его центр совпал с центром экрана
        window_geometry.moveCenter(center_point)
        # Устанавливаем новую позицию окна
        self.move(window_geometry.topLeft())

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Отменяем регистрацию горячей клавиши при закрытии окна
        if self.hotkey_handler:
            self.hotkey_handler.unregister_hotkey()

        # Проверяем, запущен ли процесс
        if self.detection_process and self.detection_process.state() == QProcess.Running:
            self.append_to_console("Закрытие приложения, остановка detection.py...", "orange")
            self.detection_process.terminate()  # Пытаемся вежливо завершить
            self.detection_process.waitForFinished(3000)  # Ждем 3 секунды
        if self.overlay_process and self.overlay_process.state() == QProcess.Running:
            self.append_to_console("Закрытие приложения, остановка overlay.py...", "orange")
            self.overlay_process.terminate()  # Пытаемся вежливо завершить
            self.overlay_process.waitForFinished(3000)  # Ждем 3 секунды
        event.accept()  # Принимаем событие закрытия (окно закроется)

    def process_detection_result(self, items):
        """Обрабатывает результат из detection.py и запускает оверлей"""
        if items:
            if self.overlay_process and self.overlay_process.state() == QProcess.Running:
                self.stop_overlay()

            # Запускаем оверлей, передавая данные через аргументы
            items_json = json.dumps(items)

            # Запускаем overlay.py как отдельный процесс
            self.overlay_process = QProcess()
            self.overlay_process.start(sys.executable, ["overlay.py", items_json])
            # Добавляем обработчик завершения оверлея
            self.overlay_process.finished.connect(self.overlay_finished)

            self.append_to_console(f"Оверлей запущен с {len(items)} предметами", "green")
        else:
            self.append_to_console("Нет предметов для отображения", "yellow")

    def overlay_finished(self, exit_code, exit_status):
        """Обработчик завершения оверлея"""
        if exit_status == QProcess.NormalExit:
            self.append_to_console(f"Оверлей завершил работу (код: {exit_code})", "yellow")
        else:
            self.append_to_console(f"overlay.py был аварийно завершен", "red")
        self.overlay_process = None

    def table_update(self):
        """Обновляет таблицу данными из top.json"""
        # Проверяем, что таблица существует
        if self.top_table is None:
            self.append_to_console("Ошибка: таблица не инициализирована", "red")
            return

        top_file = os.path.join("parse", "top.json")
        # Альтернативный путь, если первый не работает
        if not os.path.exists(top_file):
            top_file = "top.json"

        if not os.path.exists(top_file):
            self.append_to_console(f"Файл {top_file} не найден в {os.getcwd()}", "red")
            return

        try:
            with open(top_file, 'r', encoding='utf-8') as file:
                top = json.load(file)

            if not top:
                self.append_to_console("Нет данных для отображения в таблице", "yellow")
                return

            # Устанавливаем количество строк
            self.top_table.setRowCount(len(top))

            # Заполняем таблицу данными
            for row, item in enumerate(top):
                # Колонка 1: Название предмета
                name_item = QTableWidgetItem(item.get("shortName", ""))
                name_item.setToolTip(item.get("name", ""))  # Всплывающая подсказка
                name_item.setTextAlignment(Qt.AlignCenter)
                self.top_table.setItem(row, 0, name_item)

                # Колонка 2: Цена за единицу
                price = item.get("avg24hPrice", 0)
                price_item = QTableWidgetItem(f"{price:,}".replace(",", " "))
                price_item.setTextAlignment(Qt.AlignCenter)
                self.top_table.setItem(row, 1, price_item)

            self.append_to_console(f"Таблица обновлена: {len(top)} предметов", "green")

        except json.JSONDecodeError as e:
            self.append_to_console(f"Ошибка чтения JSON: {e}", "red")
        except Exception as e:
            self.append_to_console(f"Ошибка при обновлении таблицы: {e}", "red")
            traceback.print_exc()


def main():
    app = QApplication(sys.argv)  # Создаем объект QApplication
    window = MainWindow()  # Создаем экземпляр нашего главного окна
    window.show()  # Отображаем окно
    sys.exit(app.exec_())  # Запускаем цикл обработки событий и завершаем с кодом выхода


if __name__ == "__main__":
    main()