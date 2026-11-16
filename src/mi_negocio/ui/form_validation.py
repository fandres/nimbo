"""Consistent, accessible field feedback for editable forms."""
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QLineEdit, QComboBox, QScrollArea, QTabWidget,
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QTableWidget)
from ..catalog import ValidationError
from ..sales import money


def required(field, label):
    return (field, f'Completa {label}.') if not field.text().strip() else None


def choice(field, label):
    return (field, f'Selecciona {label}.') if field.currentData() is None else None


def amount_issue(field, label, positive=False):
    try:
        value = money(field.text())
        if positive and value <= 0:
            return field, f'{label}: escribe un valor mayor que cero.'
    except ValidationError:
        return field, f'{label}: escribe un importe válido, mayor o igual a cero.'
    return None


def rate_issue(field, label, maximum=None):
    try:
        value = Decimal(field.text().strip().replace(',', '.'))
        if not value.is_finite() or value < 0 or (maximum is not None and value > maximum) or value.as_tuple().exponent < -6:
            raise ValueError()
    except (InvalidOperation, ValueError):
        return field, f'{label}: escribe un porcentaje válido entre 0 y {maximum}.'
    return None


def _polish(field):
    field.style().unpolish(field)
    field.style().polish(field)
    field.update()


def clear_field(field):
    if field.property('invalid'):
        field.setProperty('invalid', False)
        field.setToolTip(field.property('validationOriginalTooltip') or '')
        _polish(field)


def check(owner, issues, error=None):
    """Mark every invalid field, reveal/focus the first; never mutate form data."""
    for field in owner.findChildren(QWidget):
        clear_field(field)
    problems = [issue for issue in issues if issue]
    if error is not None:
        error.setText('\n'.join(dict.fromkeys(message for _, message in problems)))
        error.show()
    if not problems:
        return True
    for field, message in problems:
        if not field.property('validationConnected'):
            field.setProperty('validationOriginalTooltip', field.toolTip())
            for signal in ('textChanged', 'currentIndexChanged', 'valueChanged', 'dateChanged', 'toggled'):
                if hasattr(field, signal):
                    getattr(field, signal).connect(lambda *_, w=field: clear_field(w))
                    break
            if isinstance(field, QComboBox) and field.isEditable():
                field.editTextChanged.connect(lambda *_, w=field: clear_field(w))
            field.setProperty('validationConnected', True)
        field.setProperty('invalid', True)
        field.setToolTip(message)
        _polish(field)
    field = problems[0][0]
    reveal = getattr(field, '_validation_reveal', None)
    if reveal:
        reveal()
    ancestor = field.parentWidget()
    while ancestor is not None:
        if isinstance(ancestor, QTabWidget):
            for i in range(ancestor.count()):
                if ancestor.widget(i).isAncestorOf(field):
                    ancestor.setCurrentIndex(i)
        ancestor = ancestor.parentWidget()
    field.setFocus(Qt.OtherFocusReason)
    if isinstance(field, QLineEdit):
        field.selectAll()
    elif isinstance(field, QComboBox) and field.isEditable():
        field.lineEdit().selectAll()
    def ensure_visible():
        from shiboken6 import isValid
        if not isValid(field):return
        ancestor = field.parentWidget()
        while ancestor is not None:
            if isinstance(ancestor, QScrollArea):
                ancestor.ensureWidgetVisible(field, 16, 16)
            elif isinstance(ancestor, QTableWidget):
                for row in range(ancestor.rowCount()):
                    for col in range(ancestor.columnCount()):
                        cell = ancestor.cellWidget(row, col)
                        if cell is not None and (cell is field or cell.isAncestorOf(field)):
                            ancestor.scrollTo(ancestor.model().index(row, col))
            ancestor = ancestor.parentWidget()
    ensure_visible()
    # Revealing a collapsed section schedules its new layout geometry.
    QTimer.singleShot(0, ensure_visible)
    return False


def required_reason(parent, title, prompt):
    """Keep mandatory reason prompts open until corrected or cancelled."""
    dialog = RequiredReasonDialog(parent, title, prompt)
    accepted = bool(dialog.exec())
    return dialog.field.text().strip(), accepted


class RequiredReasonDialog(QDialog):
    def __init__(self, parent=None, title='Motivo', prompt='Motivo obligatorio'):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 200)
        layout = QVBoxLayout(self)
        label = QLabel(prompt); label.setWordWrap(True); layout.addWidget(label)
        self.field = QLineEdit(); layout.addWidget(self.field)
        self.error = QLabel(); self.error.setObjectName('error'); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('Confirmar')
        buttons.button(QDialogButtonBox.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def accept(self):
        if check(self, [required(self.field, 'el motivo')], self.error):
            super().accept()
