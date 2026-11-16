"""Tab acepta únicamente una sugerencia inequívoca y continúa el formulario."""
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import QComboBox, QCompleter


class UniqueCompletionTab(QObject):
    def __init__(self, field, completer):
        super().__init__(field)
        self.field = field
        self.editor = field.lineEdit() if isinstance(field, QComboBox) else field
        self.completer = completer
        self.editor.installEventFilter(self)
        if field is not self.editor:
            field.installEventFilter(self)
        completer.popup().installEventFilter(self)

    def eventFilter(self, watched, event):
        if (event.type() != QEvent.KeyPress or event.key() != Qt.Key_Tab
                or event.modifiers() != Qt.NoModifier):
            return False
        text = self.editor.text()
        completer = self.completer
        # Expense concepts supply an already filtered model (minimum 3 characters).
        if completer.completionMode() != QCompleter.UnfilteredPopupCompletion:
            completer.setCompletionPrefix(text)
        available = (completer.completionMode() != QCompleter.UnfilteredPopupCompletion
                     or completer.popup().isVisible())
        if available and text.strip() and completer.completionCount() == 1:
            completer.setCurrentRow(0)
            choice = completer.currentCompletion()
            if isinstance(self.field, QComboBox):
                self.field.setCurrentIndex(self.field.findText(choice, Qt.MatchExactly))
            else:
                self.editor.setText(choice)
            completer.activated[str].emit(choice)
        completer.popup().hide()
        self.field.setFocus(Qt.TabFocusReason)
        self.field.focusNextPrevChild(True)
        return True


def enable_unique_tab(field, completer=None):
    completer = completer or field.completer()
    field._unique_completion_tab = UniqueCompletionTab(field, completer)
