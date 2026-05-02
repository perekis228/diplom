import html
# noinspection PyUnresolvedReferences


class ConsoleMixin:
    """Миксин для работы с консолью"""
    def __init__(self):
        super().__init__()

    def clear_console(self) -> None:
        """Очищает консоль"""
        self.console.clear()

    def append_to_console(self, text: str, color: str = None) -> None:
        """Вывод в консоль"""
        if color:
            safe_text = html.escape(text)
            colored_html = f'<font color="{color}">{safe_text}</font>'
            self.console.insertHtml(colored_html + '<br>')
        else:
            self.console.insertPlainText(text + '\n')
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
