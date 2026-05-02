import sys
import os
from PyQt5.QtCore import QProcess, QProcessEnvironment
from functools import partial


class ProcessMixin:
    def __init__(self):
        super().__init__()
        self._processes = {}
        self._stdout_handlers = {}
        self._stderr_handlers = {}
        self._finished_handlers = {}

    def _start_script(self, script_name, args, button, stdout_handler,
                      stderr_handler=None, finished_handler=None):
        process_key = script_name

        if process_key in self._processes and self._processes[process_key].state() == QProcess.Running:
            self.append_to_console(f"{process_key} уже запущен!", "orange")
            return

        if process_key in self._processes:
            self._processes[process_key].deleteLater()
            del self._processes[process_key]

        proc = QProcess()
        proc.setWorkingDirectory(self.project_root)

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", self.project_root)
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUTF8", "1")
        proc.setProcessEnvironment(env)

        proc.setProcessChannelMode(QProcess.MergedChannels)

        self._processes[process_key] = proc
        self._stdout_handlers[process_key] = stdout_handler
        if stderr_handler:
            self._stderr_handlers[process_key] = stderr_handler
        else:
            self._stderr_handlers[process_key] = lambda text: self.append_to_console(f"[STDERR] {text}", "red")
        if finished_handler:
            self._finished_handlers[process_key] = finished_handler

        proc.readyReadStandardOutput.connect(partial(self._on_process_stdout, process_key))
        proc.readyReadStandardError.connect(partial(self._on_process_stderr, process_key))
        proc.started.connect(partial(self._on_process_started, process_key, button))
        proc.finished.connect(partial(self._on_process_finished, process_key, button))
        proc.errorOccurred.connect(partial(self._on_process_error, process_key, button))

        script_path = os.path.join(self.base_dir, script_name)
        if not os.path.exists(script_path):
            self.append_to_console(f"Файл {script_path} не найден", "red")
            return

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

        if process_key in self._finished_handlers:
            self._finished_handlers[process_key](exit_code, exit_status)

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