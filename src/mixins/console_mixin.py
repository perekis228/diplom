import html


class ConsoleMixin:
    def __init__(self):
        super().__init__()

    """Миксин для работы с консолью (поиск, избранное, топ)"""
    def clear_console(self):
        """Очищает консоль"""
        self.console.clear()

    def append_to_console(self, text, color=None):
        if color:
            safe_text = html.escape(text)
            colored_html = f'<font color="{color}">{safe_text}</font>'
            self.console.insertHtml(colored_html + '<br>')
        else:
            self.console.insertPlainText(text + '\n')
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
