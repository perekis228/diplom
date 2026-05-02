import os
import sys
import ctypes
from PyQt5.QtCore import QObject, pyqtSignal
import keyboard

mixins_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(mixins_dir)
sys.path.append(src_dir)

from src.logger import log_to_file
# noinspection PyUnresolvedReferences


class HotkeyHandler(QObject):
    """Класс для работы с горячей клавишей (работает в любом окне)"""
    hotkey_pressed = pyqtSignal()
    hotkey_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.hotkey_global = None
        self.is_registered = None

    def register_hotkey(self) -> bool:
        """Регистрирует глобальную горячую клавишу"""
        try:
            if os.name == 'nt' and not self._is_admin():
                self.hotkey_error.emit(
                    "Для работы глобальной горячей клавиши требуются права администратора.\n"
                    "Перезапустите приложение от имени администратора или используйте кнопку в интерфейсе."
                )
                return False

            self.unregister_hotkey()
            self.hotkey_global = keyboard.add_hotkey('shift+l', self._on_hotkey, suppress=True)
            self.is_registered = True
            return True

        except ImportError:
            self.hotkey_error.emit("Библиотека keyboard не установлена")
            log_to_file("Библиотека keyboard не установлена", "ERROR")
            return False
        except Exception as e:
            self.hotkey_error.emit(f"Ошибка регистрации горячей клавиши: {str(e)}")
            log_to_file(f"Ошибка регистрации горячей клавиши: {str(e)}", "ERROR")
            return False

    def _on_hotkey(self) -> None:
        """Внутренний обработчик нажатия клавиши (вызывается из потока keyboard)"""
        self.hotkey_pressed.emit()

    def unregister_hotkey(self) -> None:
        """Отменяет регистрацию глобальной горячей клавиши"""
        if self.hotkey_global is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_global)
                self.hotkey_global = None
            except Exception as e:
                log_to_file(f"Ошибка отключения горячей клавиши: {e}", "ERROR")

    @staticmethod
    def _is_admin():
        """Проверяет, запущено ли приложение с правами администратора"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception as e:
            log_to_file(f"Ошибка проверки прав администратора: {e}")
            return False
