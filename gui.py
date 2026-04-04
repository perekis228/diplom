import sys
from PyQt5.QtWidgets import (QApplication,  # Главный класс приложения
                             QMainWindow,  # Класс главного окна
                             QWidget,  # Базовый виджет для контейнера
                             QVBoxLayout,  # Вертикальный менеджер компоновки
                             QHBoxLayout,  # Горизонтальный менеджер компоновки
                             QLabel,  # Текстовая метка
                             QPushButton,  # Кнопка
                             QTextEdit)  # Текстовое поле для консоли

from PyQt5.QtCore import Qt, QProcess  # Qt - константы, QProcess - для запуска внешних программ
from PyQt5.QtGui import QFont  # QFont - шрифты


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_on = False  # Флаг состояния детектора (включен/выключен)
        self.detection_process = None  # Переменная для хранения объекта процесса detection.py
        self.init_ui()  # Вызываем метод инициализации интерфейса
        self.center()  # Вызываем метод центрирования окна на экране

    def init_ui(self):
        """Метод для создания пользовательского интерфейса"""
        self.setWindowTitle("Детектор Tarkov")
        self.setGeometry(0, 0, 1100, 500)

        # Создаем центральный виджет (обязательный элемент для QMainWindow)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Создаем главный вертикальный менеджер компоновки
        main_layout = QVBoxLayout(central_widget)

        # ========== ВЕРХНЯЯ ПАНЕЛЬ С КНОПКАМИ ==========
        top_layout = QVBoxLayout()  # Создаем вертикальный layout для верхней части

        # Создаем заголовок
        title = QLabel("Детектор предметов")  # Создаем текстовую метку
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
        button_layout = QHBoxLayout()  # Горизонтальное расположение кнопок

        # Кнопка запуска detection.py
        self.run_button = QPushButton("Запустить detection.py")
        self.run_button.clicked.connect(self.run_detect)
        button_layout.addWidget(self.run_button)
        self.run_button.setEnabled(False)

        # Кнопка очистки консоли
        self.clear_button = QPushButton("Очистить консоль")
        self.clear_button.clicked.connect(self.clear_console)
        button_layout.addWidget(self.clear_button)

        top_layout.addLayout(button_layout)  # Добавляем горизонтальный layout с кнопками в верхний вертикальный layout

        main_layout.addLayout(top_layout)  # Добавляем верхнюю панель в главный layout

        # ========== КОНСОЛЬ ДЛЯ ВЫВОДА ==========
        # Создаем метку для консоли
        console_label = QLabel("Консоль вывода:")
        console_label.setFont(QFont("Arial", 10, QFont.Bold))
        main_layout.addWidget(console_label)

        # Создаем текстовое поле для консоли
        self.console = QTextEdit()
        self.console.setFont(QFont("Courier New", 10))
        self.console.setReadOnly(True)  # Запрещаем редактирование (только чтение)

        # Устанавливаем стили для консоли (темная тема)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;  /* Темно-серый фон */
                color: #d4d4d4;             /* Светло-серый текст */
                border: 1px solid #3c3c3c;  /* Серая рамка */
                border-radius: 5px;         /* Скругление углов */
            }
        """)
        main_layout.addWidget(self.console)  # Добавляем консоль в главный layout
        central_widget.setLayout(main_layout)  # Устанавливаем главный layout для центрального виджета

        # Устанавливаем начальное состояние кнопки-переключателя
        self.update_ui()

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

    def run_detect(self):
        """Запускает detection.py в отдельном процессе"""
        try:
            # Проверяем, не запущен ли уже процесс
            if self.detection_process and self.detection_process.state() == QProcess.Running:
                self.append_to_console("Процесс уже запущен!", "orange")
                return

            # Создаем новый объект QProcess (управляет внешним процессом)
            self.detection_process = QProcess()
            # Объединяем stdout (стандартный вывод) и stderr (ошибки) в один поток
            self.detection_process.setProcessChannelMode(QProcess.MergedChannels)

            # ========== ПОДКЛЮЧАЕМ СИГНАЛЫ ПРОЦЕССА ==========
            # Сигнал readyReadStandardOutput - когда есть данные в stdout
            self.detection_process.readyReadStandardOutput.connect(self.handle_stdout)
            # Сигнал readyReadStandardError - когда есть данные в stderr
            self.detection_process.readyReadStandardError.connect(self.handle_stderr)
            # Сигнал finished - когда процесс завершился
            self.detection_process.finished.connect(self.process_finished)
            # Сигнал started - когда процесс успешно запустился
            self.detection_process.started.connect(self.process_started)

            # Запускаем detection.py
            # sys.executable - путь к текущему интерпретатору Python
            self.detection_process.start(sys.executable, ["detection.py"])

            # Ждем запуска процесса максимум 3 секунды
            if not self.detection_process.waitForStarted(3000):
                self.append_to_console("Ошибка: не удалось запустить процесс", "red")
                return

            self.run_button.setEnabled(False)  # Блокируем кнопку запуска

        except Exception as e:  # Ловим любые исключения
            self.append_to_console(f"Ошибка при запуске: {e}", "red")

    def handle_stdout(self):
        """Обработка стандартного вывода"""
        if self.detection_process:
            # Читаем все данные из стандартного вывода
            data = self.detection_process.readAllStandardOutput()  # QByteArray
            # Декодируем байты в строку UTF-8, заменяем ошибки
            text = bytes(data).decode('utf-8', errors='replace')
            if text.strip():
                self.append_to_console(text.strip())

    def handle_stderr(self):
        """Обработка стандартного вывода ошибок"""
        if self.detection_process:
            # Читаем все данные из потока ошибок
            data = self.detection_process.readAllStandardError()
            # Декодируем байты в строку
            text = bytes(data).decode('utf-8', errors='replace')
            if text.strip():
                self.append_to_console(f"[ОШИБКА] {text.strip()}", "red")

    def process_started(self):
        """Обработчик запуска процесса"""
        self.append_to_console("detection.py успешно запущен!", "green")

    def process_finished(self, exit_code, exit_status):
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
            self.run_button.setEnabled(True)
        else:
            self.append_to_console("Детектор деактивирован", "yellow")
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
        # Проверяем, запущен ли процесс
        if self.detection_process and self.detection_process.state() == QProcess.Running:
            self.append_to_console("Закрытие приложения, остановка detection.py...", "orange")
            self.detection_process.terminate()  # Пытаемся вежливо завершить
            self.detection_process.waitForFinished(3000)  # Ждем 3 секунды
        event.accept()  # Принимаем событие закрытия (окно закроется)


def main():
    app = QApplication(sys.argv)  # Создаем объект QApplication
    window = MainWindow()  # Создаем экземпляр нашего главного окна
    window.show()  # Отображаем окно
    sys.exit(app.exec_())  # Запускаем цикл обработки событий и завершаем с кодом выхода


if __name__ == "__main__":
    main()