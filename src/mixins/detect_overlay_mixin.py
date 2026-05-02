import os
import sys
import json
from typing import Dict, Any
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QProcess, QTimer

mixins_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(mixins_dir)
sys.path.append(src_dir)

from src.logger import log_to_file
# noinspection PyUnresolvedReferences


class DetectOverlayMixin:
    """Миксин для работы detection.py и overlay.py"""
    def __init__(self):
        super().__init__()
        self.screenshot_path = None

    def take_screenshot_and_run(self) -> None:
        """Делает скриншот всего экрана и запускает detection.py с путем к скриншоту"""
        try:
            proc = self._processes.get("detection.py")
            if proc and proc.state() == QProcess.Running:
                self.append_to_console("Процесс уже запущен!", "orange")
                log_to_file("Попытка запуска detection.py, когда процесс уже запущен", "WARNING")
                return

            screen = QApplication.primaryScreen()
            if not screen:
                self.append_to_console("Ошибка: не удалось получить доступ к экрану", "red")
                log_to_file("Ошибка: не удалось получить доступ к экрану", "ERROR")
                return
            filename = "screenshot.png"
            self.screenshot_path = os.path.join(self.project_root, "temp", filename)

            # noinspection PyTypeChecker
            screenshot = screen.grabWindow(0)
            success = screenshot.save(self.screenshot_path, "PNG")

            if success:
                self.append_to_console(f"Скриншот сохранен: {self.screenshot_path}", "green")
                log_to_file(f"Скриншот сохранен: {self.screenshot_path}", "INFO")
                self.run_detect_with_screenshot()
            else:
                self.append_to_console("Ошибка: не удалось сохранить скриншот", "red")
                log_to_file("Ошибка: не удалось сохранить скриншот", "ERROR")

        except Exception as e:
            self.append_to_console(f"Ошибка при создании скриншота", "red")
            log_to_file(f"Ошибка при создании скриншота: {e}", "ERROR")

    def run_detect_with_screenshot(self) -> None:
        """Запуск detection.py"""
        if not self.screenshot_path or not os.path.exists(self.screenshot_path):
            self.append_to_console("Скриншот не найден", "red")
            log_to_file(f"Скриншот не найден", "ERROR")
            return

        def handle_stdout(text: str) -> None:
            try:
                items_data = json.loads(text)
                self.process_detection_result(items_data)
            except json.JSONDecodeError:
                self.append_to_console(text)

        def on_finished(exit_code: str, exit_status: str) -> None:
            if self.screenshot_path and os.path.exists(self.screenshot_path):
                try:
                    os.remove(self.screenshot_path)
                    self.append_to_console(f"Скриншот {self.screenshot_path} удалён", "gray")
                    log_to_file(f"Скриншот {self.screenshot_path} удалён", "INFO")
                except Exception as e:
                    self.append_to_console(f"Ошибка удаления скриншота", "orange")
                    log_to_file(f"Ошибка удаления скриншота: {e}", "ERROR")
                finally:
                    self.screenshot_path = None

        self._start_script(
            script_name="detection.py",
            args=[self.screenshot_path, str(self.n_items_for_detection)],
            button=self.run_button,
            stdout_handler=handle_stdout,
            finished_handler=on_finished
        )

    def process_detection_result(self, items: Dict[str, Dict[str, Any]]) -> None:
        """Запуск overlay.py с данными из detection.py"""
        if "overlay.py" in self._processes:
            self.force_stop_overlay("overlay.py")

        if not items:
            self.append_to_console("Нет предметов для отображения", "yellow")
            log_to_file("Нет предметов для отображения", "WARNING")
            return

        temp_file = os.path.join(self.project_root, "temp", "temp_detection_result.json")
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(items, f)
        except Exception as e:
            self.append_to_console(f"Ошибка сохранения файла {temp_file}", "red")
            log_to_file(f"Ошибка сохранения файла: {temp_file}\n{e}", "INFO")
            return

        def handle_stdout(text: str) -> None:
            self.append_to_console(text, "cyan")

        def handle_stderr(text: str) -> None:
            self.append_to_console(f"[ERROR] {text}", "red")

        self._start_script(
            script_name="overlay.py",
            args=[temp_file],
            button=None,
            stdout_handler=handle_stdout,
            stderr_handler=handle_stderr
        )

    def stop_overlay(self) -> None:
        """Остановка оверлея через флаг"""
        process_key = "overlay.py"
        proc = self._processes.get(process_key)
        if not proc or proc.state() != QProcess.Running:
            return

        pid = proc.processId()
        self.append_to_console(f"Остановка оверлея...", "orange")
        log_to_file(f"Остановка оверлея (PID: {pid})...", "INFO")

        flag_path = os.path.join(self.project_root, "temp", "overlay_exit.flag")
        try:
            with open(flag_path, 'w') as f:
                f.write("exit")
            self.append_to_console("Флаг завершения создан", "cyan")
            log_to_file("Флаг завершения создан", "INFO")
        except Exception as e:
            self.append_to_console(f"Ошибка создания файла-флага", "red")
            log_to_file(f"Ошибка создания файла-флага: {e}", "ERROR")

        self.append_to_console("Отправлен SIGTERM, ожидание 3 секунды...", "cyan")
        log_to_file("Отправлен SIGTERM, ожидание 3 секунды...", "INFO")
        proc.terminate()
        QTimer.singleShot(3000, lambda: self._check_overlay_terminate(process_key))

    def _check_overlay_terminate(self, process_key: str = "overlay.py") -> None:
        """Вызывается через 3 секунды после terminate. Если процесс ещё жив — убиваем."""
        proc = self._processes.get(process_key)
        if not proc:
            return
        if proc.state() != QProcess.Running:
            self.append_to_console("Оверлей успешно завершился после SIGTERM", "green")
            log_to_file("Оверлей успешно завершился после SIGTERM", "INFO")
            return
        self.append_to_console("Оверлей не ответил на SIGTERM, принудительная остановка...", "red")
        log_to_file("Оверлей не ответил на SIGTERM, принудительная остановка...", "ERROR")
        self.force_stop_overlay(process_key)

    def force_stop_overlay(self, process_key: str = "overlay.py") -> None:
        """Принудительная остановка (kill)"""
        proc = self._processes.pop(process_key, None)
        if not proc:
            return
        pid = proc.processId()
        self.append_to_console(f"Принудительное завершение процесса", "red")
        log_to_file(f"Принудительное завершение процесса {pid}", "INFO")
        proc.kill()
        proc.deleteLater()

        flag_path = os.path.join(self.project_root, "temp", "overlay_exit.flag")
        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except Exception as e:
                log_to_file(f"Ошибка удаления флага: {e}", "ERROR")
