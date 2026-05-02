import sys
import os
import ctypes
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QProcess, QTimer

mixins_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(mixins_dir)
sys.path.append(src_dir)

from src.hotkey import HotkeyHandler
from src.logger import log_to_file
# noinspection PyUnresolvedReferences


class HotkeyManagerMixin:
    """Миксин для работы с горячей клавишей"""

    def __init__(self):
        super().__init__()
        self.hotkey_handler = None

    def init_hotkey_handler(self) -> None:
        """Инициализирует обработчик горячих клавиш"""
        self.hotkey_handler = HotkeyHandler()
        self.hotkey_handler.hotkey_pressed.connect(self.on_hotkey_activated)
        self.hotkey_handler.hotkey_error.connect(self.on_hotkey_error)

    def on_hotkey_error(self, error_message: str) -> None:
        """Обработчик ошибок горячей клавиши"""
        self.append_to_console(f"{error_message}", "red")

        if "администратора" in error_message:
            # noinspection PyTypeChecker
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
        else:
            log_to_file(f"{error_message}", "ERROR")

    def restart_as_admin(self) -> None:
        """Перезапускает приложение с правами администратора"""
        try:
            if os.name == 'nt':
                bat_path = os.path.join(self.project_root, "temp", "restart_admin.bat")
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write("@echo off\n")
                    f.write(f'cd /d "{self.project_root}"\n')
                    f.write(f'set PYTHONPATH="{self.project_root}";%PYTHONPATH%\n')
                    f.write(f'"{sys.executable}" "{self.main_script}"\n')

                ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    bat_path,
                    None,
                    self.project_root,
                    0
                )
                QTimer.singleShot(500, QApplication.quit)

        except Exception as e:
            self.append_to_console(f"Ошибка перезапуска", "red")
            log_to_file(f"Ошибка перезапуска: {e}", "ERROR")

    def on_hotkey_activated(self) -> None:
        """Обработчик активации горячей клавиши Shift+L"""
        self.append_to_console("Горячая клавиша Shift+L нажата", "cyan")
        log_to_file("Горячая клавиша Shift+L нажата")

        if self.detector_is_on:
            proc = self._processes.get("overlay.py")
            if proc and proc.state() == QProcess.Running:
                self.append_to_console("Оверлей запущен, останавливаю...", "orange")
                log_to_file("Оверлей запущен, останавливаю...")
                self.stop_overlay()
            else:
                self.append_to_console("Запуск детекции...", "cyan")
                log_to_file("Запуск детекции...")
                self.take_screenshot_and_run()
        else:
            self.append_to_console("Детектор выключен. Сначала включите детектор", "orange")
            log_to_file("Попытка запуска детекции с выключенным детектором")
