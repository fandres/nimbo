"""Numeric controls with arrows visible independently of the desktop theme."""
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSpinBox, QStyle, QStyleOptionSpinBox


class NumericSpinBox(QSpinBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for control, flag, direction in (
            (QStyle.SC_SpinBoxUp, QSpinBox.StepEnabledFlag.StepUpEnabled, -1),
            (QStyle.SC_SpinBoxDown, QSpinBox.StepEnabledFlag.StepDownEnabled, 1),
        ):
            rect = self.style().subControlRect(QStyle.CC_SpinBox, option, control, self)
            if rect.isEmpty():
                continue
            enabled = self.isEnabled() and bool(option.stepEnabled & flag)
            painter.setPen(QPen(QColor('#233e70' if enabled else '#a7b2c4'), 1.8))
            center = rect.center()
            x, y = center.x(), center.y()
            painter.drawPolyline(QPolygonF([
                QPointF(x - 4, y - direction * 2),
                QPointF(x, y + direction * 2),
                QPointF(x + 4, y - direction * 2),
            ]))
        painter.end()
