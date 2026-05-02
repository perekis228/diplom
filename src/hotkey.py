import os
import ctypes
from PyQt5.QtCore import (
    QObject,
    pyqtSignal
)
import keyboard


class HotkeyHandler(QObject):
    hotkey_pressed = pyqtSignal()
    hotkey_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.hotkey_global = None

    def register_hotkey(self):
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
            return False
        except Exception as e:
            self.hotkey_error.emit(f"Ошибка регистрации горячей клавиши: {str(e)}")
            return False

    def _on_hotkey(self):
        """Внутренний обработчик нажатия клавиши (вызывается из потока keyboard)"""
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
