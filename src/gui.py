import sys
import os
import ctypes
import html
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
    QTableWidgetItem,
    QHeaderView,
    QSpinBox,
    QLineEdit,
    QMenu,
    QAction,
    QMessageBox
)
from PyQt5.QtCore import (
    Qt,
    QProcess,
    QObject,
    pyqtSignal,
    QTimer,
    QProcessEnvironment
)
from PyQt5.QtGui import QFont
import keyboard
import json
import traceback
from functools import partial
from Switch import Switch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
sys.stdout.reconfigure(encoding='utf-8')  # type:ignore


# Создаем класс-посредник для обработки горячих клавиш в отдельном потоке
class HotkeyHandler(QObject):
    # Создаем сигнал, который будет испускаться при нажатии горячей клавиши
    hotkey_pressed = pyqtSignal()
    hotkey_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.hotkey_global = None  # Идентификатор глобальной горячей клавиши

    def register_hotkey(self):
        """Регистрирует глобальную горячую клавишу"""
        try:
            # Проверяем права администратора в Windows
            if os.name == 'nt' and not self._is_admin():
                self.hotkey_error.emit(
                    "Для работы глобальной горячей клавиши требуются права администратора.\n"
                    "Перезапустите приложение от имени администратора или используйте кнопку в интерфейсе."
                )
                return False

            # Регистрируем горячую клавишу
            self.unregister_hotkey()
            self.hotkey_global = keyboard.add_hotkey('shift+l', self._on_hotkey, suppress=True)
            self.is_registered = True
            return True

        except ImportError:
            self.hotkey_error.emit("Библиотека keyboard не установлена")
            return False
        except Exception as e:
            self.hotkey_error.emit(f"Ошибка регистрации горячей клавиши: {str(e)}")
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

    @staticmethod
    def _is_admin():
        """Проверяет, запущено ли приложение с правами администратора"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        for sub in ("temp", "data", "logs"):
            path = os.path.join(PROJECT_ROOT, sub)
            os.makedirs(path, exist_ok=True)
        self._processes = {}
        self._stdout_handlers = {}
        self._stderr_handlers = {}
        self._finished_handlers = {}
        self.is_on = False  # Флаг состояния детектора (включен/выключен)
        self.screenshot_path = None  # Путь к последнему сделанному скриншоту
        self.hotkey_handler = None  # Обработчик горячих клавиш
        self.all_items_data = {}  # Хранение всех предметов
        self.favorite_items_data = {}  # Хранение избранного
        self.search_timer = QTimer()  # Задержка поиска предметов
        self.search_timer.setSingleShot(True)  # Таймер сработает только один раз
        self.search_timer.timeout.connect(self.on_search_text_changed)  # Подключаем к методу поиска
        self.current_search_text = ""  # Текущий текст поиска
        self.n_items_for_detection = 5
        self.init_ui()  # Вызываем метод инициализации интерфейса
        self.center()  # Вызываем метод центрирования окна на экране
        self.init_hotkey_handler()  # Инициализируем обработчик горячих клавиш
        flag_path = os.path.join(PROJECT_ROOT, "temp", "overlay_exit.flag")

        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except:
                pass

    def init_hotkey_handler(self):
        """Инициализирует обработчик горячих клавиш"""
        self.hotkey_handler = HotkeyHandler()
        # Подключаем сигнал из потока keyboard к слоту в основном потоке GUI
        self.hotkey_handler.hotkey_pressed.connect(self.on_hotkey_activated)
        self.hotkey_handler.hotkey_error.connect(self.on_hotkey_error)

    def init_ui(self):
        """Метод для создания пользовательского интерфейса"""
        self.setWindowTitle("Детектор Tarkov")
        self.setGeometry(0, 0, 1800, 800)

        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Главный горизонтальный layout (три колонки)
        main_layout = QHBoxLayout(central_widget)

        # Создаём все колонки
        main_layout.addLayout(self._create_first_column(), 30)  # Кнопки + консоль
        main_layout.addLayout(self._create_second_column(), 35)  # Топ предметов
        main_layout.addLayout(self._create_third_column(), 25)  # Поиск
        main_layout.addLayout(self._create_fourth_column(), 25)  # Избранное

        # Загружаем данные
        items_file = os.path.join(PROJECT_ROOT, "data", "tarkov_items.json")
        self.load_items_data(items_file, self.all_items_data)

        # Устанавливаем начальное состояние
        self.update_ui()

        self._del_log()

    def _create_first_column(self):
        """Создаёт первую колонку (кнопки + консоль)"""
        layout = QVBoxLayout()

        # Верхняя панель с кнопками
        layout.addLayout(self._create_top_panel())

        # Консоль вывода
        layout.addWidget(QLabel("Консоль вывода:"))
        layout.addWidget(self._create_console())

        return layout

    def _create_top_panel(self):
        """Создаёт панель с заголовком и кнопками управления"""
        layout = QVBoxLayout()

        # Заголовок
        title = QLabel("Детектор предметов")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(30)

        # Кнопка-переключатель
        self.toggle_button = self._create_toggle_button()
        layout.addWidget(self.toggle_button, alignment=Qt.AlignCenter)
        layout.addSpacing(20)

        # Switch для выбора количества предметов
        self.switch = Switch()
        self.switch.switchToggled.connect(self.on_switch_toggled)
        layout.addWidget(self.switch, alignment=Qt.AlignCenter)

        # Кнопки управления
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

        # Кнопка парсинга цен
        self.parse_button = QPushButton("Обновить цены")
        self.parse_button.clicked.connect(self.parse)
        layout.addWidget(self.parse_button)

        # Кнопка очистки консоли
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

        # Кнопка очистки
        del_button = QPushButton("Очистить избранное")
        del_button.clicked.connect(self.clear_favorite)
        layout.addWidget(del_button)

        # Таблица избранного
        layout.addWidget(self._create_favorite_table())

        # Загружаем данные
        favorite_file = os.path.join(PROJECT_ROOT, "data", "favorite.json")
        self.load_items_data(favorite_file, self.favorite_items_data)
        self.favorite_table_update()

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

    def _get_table_style(self):
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

    def _del_log(self):
        log_path = os.path.join(PROJECT_ROOT, "logs", "tarkov_detector.log")
        if os.path.exists(log_path):
            try:
                os.remove(log_path)
            except Exception as e:
                self.append_to_console(f"Ошибка удаления лога: {e}", "orange")

    def on_hotkey_error(self, error_message):
        """Обработчик ошибок горячей клавиши"""
        self.append_to_console(f"❌ {error_message}", "red")

        # Показываем диалог с предложением перезапуска от администратора
        if "администратора" in error_message:
            reply = QMessageBox.question(
                self,
                "Требуются права администратора",
                "Для работы глобальной горячей клавиши (Shift+L) требуются права администратора.\n\n"
                "Хотите перезапустить приложение с правами администратора?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.restart_as_admin()

    def restart_as_admin(self):
        """Перезапускает приложение с правами администратора"""
        try:
            if os.name == 'nt':
                # Запускаем текущий скрипт с правами администратора
                ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    sys.executable,
                    " ".join(sys.argv),
                    None,
                    0
                )
                QApplication.quit()
        except Exception as e:
            self.append_to_console(f"Не удалось перезапустить с правами администратора: {e}", "red")

    def on_switch_toggled(self, checked):
        """Срабатывает при изменении состояния"""
        if checked:
            self.n_items_for_detection = 10
            self.append_to_console(f"Отображение 10 предметов")
        else:
            self.n_items_for_detection = 5
            self.append_to_console(f"Отображение 5 предметов")

    def clear_favorite(self):
        try:
            self.favorite_items_data.clear()
            favorite_path = os.path.join(PROJECT_ROOT, "data", "favorite.json")

            to_load = {"items": self.favorite_items_data}
            if os.path.exists(favorite_path):
                with open(favorite_path, 'w', encoding='utf-8') as f:
                    json.dump(to_load, f)
            self.favorite_table_update()
            self.append_to_console("Избранное очищено")
        except Exception as e:
            self.append_to_console(f"Не удалось очистить избранное: {str(e)}")

    def favorite_table_update(self):
        """Обновление таблицы favorite"""
        try:
            if not hasattr(self, 'favorite_table') or self.favorite_table is None:
                return

            # Блокируем сигналы таблицы на время обновления
            self.favorite_table.blockSignals(True)

            # Очищаем таблицу
            self.favorite_table.setRowCount(0)

            # Сортировка
            sorted_data = dict(sorted(self.favorite_items_data.items()))

            # Устанавливаем количество строк
            self.favorite_table.setRowCount(len(sorted_data))

            for row, (shortname, item) in enumerate(sorted_data.items()):
                try:
                    # Колонка 1: Короткое название предмета
                    shortname_item = QTableWidgetItem(shortname)
                    shortname_item.setTextAlignment(Qt.AlignCenter)
                    self.favorite_table.setItem(row, 0, shortname_item)

                    # Колонка 2: Полное название
                    name = str(item.get("name", ""))
                    name_item = QTableWidgetItem(name)
                    name_item.setTextAlignment(Qt.AlignCenter)
                    name_item.setToolTip(name)
                    self.favorite_table.setItem(row, 1, name_item)

                    # Колонка 3: Цена
                    price = item.get("price")
                    price_item = QTableWidgetItem(price)
                    price_item.setTextAlignment(Qt.AlignCenter)
                    self.favorite_table.setItem(row, 2, price_item)

                except Exception as e:
                    print(f"Ошибка при добавлении строки {row}: {e}")
                    continue

            # Разблокируем сигналы
            self.favorite_table.blockSignals(False)

        except Exception as e:
            print(f"Ошибка при обновлении таблицы: {e}")
        finally:
            try:
                self.search_table.blockSignals(False)
            except Exception:
                pass

    def show_context_menu(self, position):
        # Таблица, которая вызвала сигнал
        table = self.sender()

        # Координаты в индекс ячейки
        index = table.indexAt(position)

        if index.isValid():
            # Всплывающее окно
            menu = QMenu()
            if table != self.favorite_table:
                add_to_favorite_action = QAction("Добавить в избранное", table)
                # Подключаем триггер и передаем только номер строки
                add_to_favorite_action.triggered.connect(partial(self.add_to_favorite, table, index.row()))
                menu.addAction(add_to_favorite_action)

            del_from_favorite_action = QAction("Удалить из избранного", table)
            del_from_favorite_action.triggered.connect(partial(self.del_from_favorite, table, index.row()))
            menu.addAction(del_from_favorite_action)
            # Показывает меню и блокирует выполнение кода, пока пользователь не выберет пункт или не кликнет мимо
            menu.exec_(table.viewport().mapToGlobal(position))

    def add_to_favorite(self, table, row):
        try:
            short_name = table.item(row, 0).text()
            name = table.item(row, 1).text()
            price = table.item(row, 2).text()

            favorite_path = os.path.join(PROJECT_ROOT, "data", "favorite.json")

            favorites = {}
            if os.path.exists(favorite_path):
                try:
                    with open(favorite_path, 'r', encoding='utf-8') as f:
                        favorites = json.load(f).get("items", {})
                except (json.JSONDecodeError, FileNotFoundError):
                    favorites = {}

            # Проверяем, есть ли уже такой товар в избранном
            if short_name in favorites:
                self.append_to_console(f"Товар '{short_name}' уже есть в избранном")
                return

            # Добавляем новый элемент
            favorites[short_name] = {
                "name": name,
                "price": price
            }

            to_load = {"items": favorites}
            # Сохраняем в файл
            with open(favorite_path, 'w', encoding='utf-8') as f:
                json.dump(to_load, f, ensure_ascii=False, indent=4)

            self.append_to_console(f"Товар '{short_name}' добавлен в избранное")
            self.favorite_items_data = favorites
            self.favorite_table_update()

        except Exception as e:
            self.append_to_console(f"Не удалось сохранить в избранное: {str(e)}")

    def del_from_favorite(self, table, row):
        try:
            short_name = table.item(row, 0).text()

            favorite_path = os.path.join(PROJECT_ROOT, "data", "favorite.json")

            favorite = {}
            if os.path.exists(favorite_path):
                with open(favorite_path, 'r', encoding='utf-8') as f:
                    favorite = json.load(f).get("items", {})

            if short_name not in favorite:
                self.append_to_console(f"Товара '{short_name}' нет в избранном")
                return
            del favorite[short_name]

            to_save = {"items": favorite}
            # Сохраняем в файл
            with open(favorite_path, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, ensure_ascii=False, indent=4)

            self.favorite_items_data = favorite
            self.append_to_console(f"Товар '{short_name}' удалён из избранного")
            self.favorite_table_update()

        except Exception as e:
            self.append_to_console(f"Не удалось сохранить в избранное: {str(e)}")

    def perform_search(self, text):
        """Выполняет поиск с текущим текстом"""
        self.current_search_text = text

        if not self.current_search_text or len(text) < 2:
            self.search_table.setRowCount(0)
            self.search_results_label.setText("Найдено предметов: 0")
            return

        self.search_timer.start(300)

    def on_search_text_changed(self):
        """Обработчик изменения текста в поле поиска"""
        try:
            self.append_to_console(f"Поиск: '{self.current_search_text}'")

            if not hasattr(self, 'all_items_data') or not self.all_items_data:
                print("items_data пуст или не существует")
                return

            search_text = self.current_search_text.lower()
            filtered_items = []

            # Обычный поиск по всем предметам
            for item_shortname, item_data in self.all_items_data.items():
                try:
                    name = item_data.get("name", "")

                    if not isinstance(name, str):
                        name = str(name)

                    if search_text in item_shortname.lower() or search_text in name.lower():
                        price = item_data.get("price")

                        if price is None:
                            price = None  # Явно указываем, что данных нет
                        else:
                            # Пробуем преобразовать в число
                            try:
                                price = int(price)
                            except (ValueError, TypeError):
                                price = None

                        filtered_items.append({
                            "shortname": str(item_shortname),
                            "name": name,
                            "price": price
                        })
                except Exception as e:
                    print(f"Ошибка обработки предмета {item_shortname}: {e}")
                    continue

            # Сортировка по цене (от дорогих к дешевым)
            try:
                filtered_items.sort(key=lambda x: (x["price"] is not None, x["price"] or 0), reverse=True)
            except Exception as sort_error:
                print(f"Ошибка при сортировке: {sort_error}")
                # Если не удалось отсортировать, оставляем как есть

            # Обновляем таблицу
            self.update_search_table(filtered_items)
            self.search_results_label.setText(f"Найдено предметов: {len(filtered_items)}")

        except Exception as e:
            print(f"Ошибка в поиске: {e}")
            traceback.print_exc()

    def _start_script(self, script_name, args, button, stdout_handler,
                      stderr_handler=None, finished_handler=None):
        process_key = script_name  # можно совпадает с именем скрипта

        # Проверка, не запущен ли уже такой процесс
        if process_key in self._processes and self._processes[process_key].state() == QProcess.Running:
            self.append_to_console(f"{process_key} уже запущен!", "orange")
            return

        # Если процесс мёртв, удаляем его
        if process_key in self._processes:
            self._processes[process_key].deleteLater()
            del self._processes[process_key]

        # Создаём процесс
        proc = QProcess()
        proc.setWorkingDirectory(PROJECT_ROOT)

        # Окружение
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", PROJECT_ROOT)
        env.insert("PYTHONIOENCODING", "utf-8")
        # Для detection дополнительно PYTHONUTF8, можно всегда добавлять
        env.insert("PYTHONUTF8", "1")
        proc.setProcessEnvironment(env)

        proc.setProcessChannelMode(QProcess.MergedChannels)

        # Сохраняем ссылку на процесс и обработчики
        self._processes[process_key] = proc
        self._stdout_handlers[process_key] = stdout_handler
        if stderr_handler:
            self._stderr_handlers[process_key] = stderr_handler
        else:
            self._stderr_handlers[process_key] = lambda text: self.append_to_console(f"[STDERR] {text}", "red")
        if finished_handler:
            self._finished_handlers[process_key] = finished_handler

        # Подключаем сигналы
        proc.readyReadStandardOutput.connect(lambda: self._on_process_stdout(process_key))
        proc.readyReadStandardError.connect(lambda: self._on_process_stderr(process_key))
        proc.started.connect(lambda: self._on_process_started(process_key, button))
        proc.finished.connect(lambda exit_code, exit_status:
                              self._on_process_finished(process_key, button, exit_code, exit_status))
        proc.errorOccurred.connect(lambda error: self._on_process_error(process_key, button, error))

        # Полный путь к скрипту
        script_path = os.path.join(BASE_DIR, script_name)
        if not os.path.exists(script_path):
            self.append_to_console(f"Файл {script_path} не найден", "red")
            return

        # Запускаем
        proc.start(sys.executable, [script_path] + args)

    def _on_process_stdout(self, process_key):
        proc = self._processes.get(process_key)
        if not proc:
            return
        data = proc.readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='replace').strip()
        if text and self._stdout_handlers.get(process_key):
            self._stdout_handlers[process_key](text)

    def _on_process_stderr(self, process_key):
        proc = self._processes.get(process_key)
        if not proc:
            return
        data = proc.readAllStandardError()
        text = bytes(data).decode('utf-8', errors='replace').strip()
        if text and process_key in self._stderr_handlers:
            self._stderr_handlers[process_key](text)

    def _on_process_started(self, process_key, button):
        self.append_to_console(f"{process_key} успешно запущен!", "green")
        if button:
            button.setEnabled(False)

    def _on_process_finished(self, process_key, button, exit_code, exit_status):
        if exit_status == QProcess.NormalExit:
            self.append_to_console(f"{process_key} завершился с кодом {exit_code}", "yellow")
        else:
            self.append_to_console(f"{process_key} аварийно завершён", "red")

        if button:
            button.setEnabled(True)

        # Вызов дополнительного обработчика, если есть
        if process_key in self._finished_handlers:
            self._finished_handlers[process_key](exit_code, exit_status)

        # Очистка
        proc = self._processes.pop(process_key, None)
        if proc:
            proc.deleteLater()

    def _on_process_error(self, process_key, button, error):
        error_messages = {
            QProcess.FailedToStart: "Не удалось запустить процесс",
            QProcess.Crashed: "Процесс упал",
            QProcess.Timedout: "Таймаут процесса",
            QProcess.WriteError: "Ошибка записи",
            QProcess.ReadError: "Ошибка чтения",
            QProcess.UnknownError: "Неизвестная ошибка"
        }
        msg = error_messages.get(error, f"Ошибка {error}")
        self.append_to_console(f"Ошибка процесса {process_key}: {msg}", "red")
        if button:
            button.setEnabled(True)

    def update_search_table(self, items):
        """Обновление таблицы результатов поиска"""
        try:
            if not hasattr(self, 'search_table') or self.search_table is None:
                return

            # Блокируем сигналы таблицы на время обновления
            self.search_table.blockSignals(True)

            # Очищаем таблицу
            self.search_table.setRowCount(0)

            # Если нет предметов - выходим
            if not items:
                self.search_table.blockSignals(False)
                return

            # Устанавливаем количество строк
            self.search_table.setRowCount(len(items))

            for row, item in enumerate(items):
                try:
                    # Колонка 1: Короткое название предмета
                    shortname = str(item.get("shortname", ""))
                    shortname_item = QTableWidgetItem(shortname)
                    shortname_item.setTextAlignment(Qt.AlignCenter)
                    self.search_table.setItem(row, 0, shortname_item)

                    # Колонка 2: Полное название
                    name = str(item.get("name", ""))
                    name_item = QTableWidgetItem(name)
                    name_item.setTextAlignment(Qt.AlignCenter)
                    name_item.setToolTip(name)
                    self.search_table.setItem(row, 1, name_item)

                    # Колонка 3: Цена
                    price = item.get("price")
                    if price is None:
                        price_str = "Н/Д"
                    elif isinstance(price, int):
                        price_str = f"{int(price):,}".replace(",", " ")
                    else:
                        try:
                            # Пробуем преобразовать в число
                            price_num = int(price)
                            price_str = f"{price_num:,}".replace(",", " ")
                        except (ValueError, TypeError):
                            price_str = str(price)

                    price_item = QTableWidgetItem(price_str)
                    price_item.setTextAlignment(Qt.AlignCenter)
                    self.search_table.setItem(row, 2, price_item)

                except Exception as e:
                    print(f"Ошибка при добавлении строки {row}: {e}")
                    continue

            # Разблокируем сигналы
            self.search_table.blockSignals(False)

        except Exception as e:
            print(f"Ошибка при обновлении таблицы: {e}")
        finally:
            try:
                self.search_table.blockSignals(False)
            except Exception:
                pass

    def load_items_data(self, items_file, items_data):
        """Загружает данные из json"""
        try:
            if not os.path.exists(items_file):
                self.append_to_console(f"Файл {items_file} не найден", "red")
                items_data.clear()
                return

            with open(items_file, 'r', encoding='utf-8') as file:
                loaded_data = json.load(file).get("items", {})

            if isinstance(loaded_data, dict):
                items_data.clear()
                items_data.update(loaded_data)
            else:
                self.append_to_console(f"Ошибка: ожидался словарь, получен {type(loaded_data)}", "red")
                items_data.clear()
                return

            self.append_to_console(f"Загружено {len(items_data)} предметов из {items_file}", "green")

        except Exception as e:
            print(f"Ошибка при загрузке данных: {e}")
            traceback.print_exc()

    def on_hotkey_activated(self):
        """Обработчик активации горячей клавиши Shift+L"""
        self.append_to_console("Горячая клавиша Shift+L нажата", "cyan")

        if self.is_on:
            # Если оверлей запущен - останавливаем
            proc = self._processes.get("overlay.py")
            if proc and proc.state() == QProcess.Running:
                self.append_to_console("Оверлей запущен, останавливаю...", "orange")
                self.stop_overlay()
            else:
                # Иначе запускаем детекцию
                self.append_to_console("Запуск детекции...", "cyan")
                self.take_screenshot_and_run()
        else:
            self.append_to_console("Детектор выключен. Сначала включите детектор", "orange")

    def parse(self):
        # Специфичный аргумент: количество предметов
        num_of_items = self.number_spinbox.value()

        # Обработчик вывода (просто печатаем в консоль)
        def handle_stdout(text):
            self.append_to_console(text)

        # После завершения обновим таблицу, если парсинг успешен
        def on_finished(exit_code, exit_status):
            if exit_status == QProcess.NormalExit and exit_code == 0:
                self.top_table_update()
                items_file = os.path.join(PROJECT_ROOT, "data", "tarkov_items.json")
                self.load_items_data(items_file, self.all_items_data)

        self._start_script(
            script_name="parser.py",
            args=[str(num_of_items)],
            button=self.parse_button,
            stdout_handler=handle_stdout,
            finished_handler=on_finished
        )

    def take_screenshot_and_run(self):
        """Делает скриншот всего экрана и запускает detection.py с путем к скриншоту"""
        try:
            proc = self._processes.get("detection.py")
            if proc and proc.state() == QProcess.Running:
                self.append_to_console("Процесс уже запущен!", "orange")
                return

            screen = QApplication.primaryScreen()
            if not screen:
                self.append_to_console("Ошибка: не удалось получить доступ к экрану", "red")
                return
            filename = "screenshot.png"
            self.screenshot_path = os.path.join(PROJECT_ROOT, "temp", filename)  # Полный путь

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
        # Скриншот уже сделан в take_screenshot_and_run, путь в self.screenshot_path
        if not self.screenshot_path or not os.path.exists(self.screenshot_path):
            self.append_to_console("Скриншот не найден", "red")
            return

        def handle_stdout(text):
            # Парсим JSON – специфичная логика detection
            try:
                items_data = json.loads(text)
                self.process_detection_result(items_data)
            except json.JSONDecodeError:
                self.append_to_console(text)

        def on_finished(exit_code, exit_status):
            # Удаляем скриншот после обработки
            if self.screenshot_path and os.path.exists(self.screenshot_path):
                try:
                    os.remove(self.screenshot_path)
                    self.append_to_console(f"Скриншот {self.screenshot_path} удалён", "gray")
                except Exception as e:
                    self.append_to_console(f"Ошибка удаления: {e}", "orange")
                finally:
                    self.screenshot_path = None

        self._start_script(
            script_name="detection.py",
            args=[self.screenshot_path, str(self.n_items_for_detection)],
            button=self.run_button,
            stdout_handler=handle_stdout,
            finished_handler=on_finished
        )

    def append_to_console(self, text, color=None):
        if color:
            safe_text = html.escape(text)
            colored_html = f'<font color="{color}">{safe_text}</font>'
            self.console.insertHtml(colored_html + '<br>')
        else:
            self.console.insertPlainText(text + '\n')
        # автопрокрутка
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_console(self):
        """Очищает консоль"""
        self.console.clear()

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
        """Закрытие главного окна"""
        self.append_to_console("Закрытие приложения...", "orange")

        for key, proc in self._processes.items():
            if proc.state() == QProcess.Running:
                proc.terminate()
                proc.waitForFinished(1000)

        # Отменяем горячую клавишу
        if self.hotkey_handler:
            self.hotkey_handler.unregister_hotkey()

        temp_files = [
            os.path.join(PROJECT_ROOT, "temp", "screenshot.png"),
            os.path.join(PROJECT_ROOT, "temp", "temp_detection_result.json"),
            os.path.join(PROJECT_ROOT, "temp", "overlay_exit.flag")
        ]

        for filepath in temp_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass

        event.accept()

    def process_detection_result(self, items):
        if "overlay.py" in self._processes:
            self.force_stop_overlay("overlay.py")

        if not items:
            self.append_to_console("Нет предметов для отображения", "yellow")
            return

        # Сохраняем данные во временный файл
        temp_file = os.path.join(PROJECT_ROOT, "temp", "temp_detection_result.json")
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(items, f)
        except Exception as e:
            self.append_to_console(f"Ошибка сохранения файла: {e}", "red")
            return

        # Обработчики для overlay
        def handle_stdout(text):
            self.append_to_console(text, "cyan")

        def handle_stderr(text):
            self.append_to_console(f"[Overlay ERROR] {text}", "red")

        # Overlay не блокирует кнопки (запускается автоматически)
        self._start_script(
            script_name="overlay.py",
            args=[temp_file],
            button=None,  # нечего блокировать
            stdout_handler=handle_stdout,
            stderr_handler=handle_stderr
        )

    def stop_overlay(self):
        process_key = "overlay.py"
        proc = self._processes.get(process_key)
        if not proc or proc.state() != QProcess.Running:
            self.append_to_console("Оверлей не запущен", "yellow")
            return

        pid = proc.processId()
        self.append_to_console(f"Остановка оверлея (PID: {pid})...", "orange")

        flag_path = os.path.join(PROJECT_ROOT, "temp", "overlay_exit.flag")
        try:
            with open(flag_path, 'w') as f:
                f.write("exit")
            self.append_to_console("Файл завершения создан", "cyan")
        except Exception as e:
            self.append_to_console(f"Ошибка создания файла-флага: {e}", "red")

        self.append_to_console("Отправлен SIGTERM, ожидание 3 секунды...", "cyan")
        proc.terminate()
        QTimer.singleShot(3000, lambda: self._check_overlay_terminate(process_key))

    def _check_overlay_terminate(self, process_key="overlay.py"):
        """Вызывается через 3 секунды после terminate. Если процесс ещё жив — убиваем."""
        proc = self._processes.get(process_key)
        if not proc:
            return
        if proc.state() != QProcess.Running:
            self.append_to_console("Оверлей успешно завершился после SIGTERM", "green")
            # Очистка произойдёт в overlay_finished
            return
        # Процесс всё ещё запущен — принудительно kill
        self.append_to_console("Оверлей не ответил на SIGTERM, принудительная остановка...", "red")
        self.force_stop_overlay(process_key)

    def force_stop_overlay(self, process_key="overlay.py"):
        """Принудительная остановка"""
        proc = self._processes.pop(process_key, None)
        if not proc:
            return
        pid = proc.processId()
        self.append_to_console(f"Принудительное завершение процесса {pid}", "red")
        proc.kill()
        proc.deleteLater()

        flag_path = os.path.join(PROJECT_ROOT, "temp", "overlay_exit.flag")
        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except:
                pass

    def top_table_update(self):
        """Обновляет таблицу данными из top.json"""
        # Проверяем, что таблица существует
        if self.top_table is None:
            self.append_to_console("Ошибка: таблица не инициализирована", "red")
            return

        top_file = os.path.join(PROJECT_ROOT, "data", "top.json")

        if not os.path.exists(top_file):
            self.append_to_console(f"Файл {top_file} не найден в {os.getcwd()}", "red")
            return

        try:
            with open(top_file, 'r', encoding='utf-8') as file:
                top = json.load(file).get("items", {})

            if not top:
                self.append_to_console("Нет данных для отображения в таблице", "yellow")
                return

            # Устанавливаем количество строк
            self.top_table.setRowCount(len(top))

            # Заполняем таблицу данными
            for row, (shortname, item_data) in enumerate(top.items()):
                # Колонка 1: Название предмета
                name_item = QTableWidgetItem(shortname)
                name_item.setToolTip(item_data.get("name", ""))  # Всплывающая подсказка
                name_item.setTextAlignment(Qt.AlignCenter)
                self.top_table.setItem(row, 0, name_item)

                # Колонка 2: Цена за единицу
                price = item_data.get("avg24hPrice", 0)
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