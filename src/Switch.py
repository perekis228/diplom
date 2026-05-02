from PyQt5.QtCore import (
    Qt,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    QRectF
)
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QBrush,
    QPen
)
from PyQt5.QtWidgets import QAbstractButton

DEFAULT_WIDTH = 90
DEFAULT_HEIGHT = 45
DEFAULT_MARGIN = 3


class Switch(QAbstractButton):
    """Кастомный переключатель (switch) c анимацией и текстом внутри ползунка."""
    switchToggled = pyqtSignal(bool)

    def __init__(
            self,
            parent=None,
            width: int = DEFAULT_WIDTH,
            height: int = DEFAULT_HEIGHT,
            margin: float = DEFAULT_MARGIN,
            text_off: str = "5",
            text_on: str = "10"
    ) -> None:
        """Инициализация переключателя с фиксированным размером и анимацией."""
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.toggled.connect(self._on_toggled)  # type:ignore
        self.setChecked(False)
        self._margin = margin
        self._knob_x = margin

        self._text_off = text_off
        self._text_on = text_on

        self.animation = QPropertyAnimation(self, b"knob_x")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

    def _on_toggled(self, checked: bool):
        """Запускает анимацию и отправляет кастомный сигнал."""
        self.start_animation()
        self.switchToggled.emit(checked)  # type:ignore

    def nextCheckState(self) -> None:
        """Переключатель состояния."""
        self.setChecked(not self.isChecked())

    @pyqtProperty(float)
    def knob_x(self) -> float:
        """Геттер отступа для анимации."""
        return self._knob_x

    @knob_x.setter
    def knob_x(self, value: float) -> None:
        """Сеттер отступа для анимации."""
        self._knob_x = value
        self.update()

    def start_animation(self) -> None:
        """Запуск анимации переключения ползунка."""
        self.animation.stop()
        if self.isChecked():
            target = self.width() - self.height() + self._margin
        else:
            target = self._margin

        self.animation.setStartValue(self._knob_x)
        self.animation.setEndValue(target)
        self.animation.start()

    def paintEvent(self, event) -> None:
        """Отрисовка свитча."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = self.height() // 2

        # Фон
        if self.isChecked():
            bg_color = QColor(0, 150, 136)  # Бирюзовый
            text = self._text_on
        else:
            bg_color = QColor(150, 150, 150)  # Серый
            text = self._text_off

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), radius, radius)

        circle_size = int(self.height() - 2 * self._margin)
        circle_x = int(self._knob_x)
        circle_y = int(self._margin)

        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(circle_x, circle_y, circle_size, circle_size)

        circle_rect = QRectF(circle_x, circle_y, circle_size, circle_size)

        painter.save()
        font = painter.font()
        font.setPointSize(int(circle_size) // 3)
        painter.setFont(font)
        painter.setPen(QPen(QColor(0, 0, 0)))
        painter.drawText(circle_rect, Qt.AlignCenter, text)
        painter.restore()

    def mousePressEvent(self, event) -> None:
        """Функция, которая активируется при нажатии мышкой на область свитча."""
        self.nextCheckState()
