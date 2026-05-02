import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QProcess, QTimer
import json


class DetectOverlayMixin:
    def __init__(self):
        super().__init__()
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
            self.screenshot_path = os.path.join(self.project_root, "temp", filename)

            screenshot = screen.grabWindow(0)
            success = screenshot.save(self.screenshot_path, "PNG")

            if success:
                self.append_to_console(f"Скриншот сохранен: {self.screenshot_path}", "green")
                self.run_detect_with_screenshot()
            else:
                self.append_to_console("Ошибка: не удалось сохранить скриншот", "red")

        except Exception as e:
            self.append_to_console(f"Ошибка при создании скриншота: {e}", "red")

    def run_detect_with_screenshot(self):
        if not self.screenshot_path or not os.path.exists(self.screenshot_path):
            self.append_to_console("Скриншот не найден", "red")
            return

        def handle_stdout(text):
            try:
                items_data = json.loads(text)
                self.process_detection_result(items_data)
            except json.JSONDecodeError:
                self.append_to_console(text)

        def on_finished(exit_code, exit_status):
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

    def process_detection_result(self, items):
        if "overlay.py" in self._processes:
            self.force_stop_overlay("overlay.py")

        if not items:
            self.append_to_console("Нет предметов для отображения", "yellow")
            return

        temp_file = os.path.join(self.project_root, "temp", "temp_detection_result.json")
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(items, f)
        except Exception as e:
            self.append_to_console(f"Ошибка сохранения файла: {e}", "red")
            return

        def handle_stdout(text):
            self.append_to_console(text, "cyan")

        def handle_stderr(text):
            self.append_to_console(f"[Overlay ERROR] {text}", "red")

        self._start_script(
            script_name="overlay.py",
            args=[temp_file],
            button=None,
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

        flag_path = os.path.join(self.project_root, "temp", "overlay_exit.flag")
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
            return
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

        flag_path = os.path.join(self.project_root, "temp", "overlay_exit.flag")
        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except:
                pass