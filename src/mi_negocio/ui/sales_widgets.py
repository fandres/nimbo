"""Controles comunes para importes y pagos."""
from PySide6.QtCore import QDate, QEvent, Qt, QPointF, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLineEdit, QDateEdit, QComboBox, QLabel, QStyle, QStyleOptionSpinBox
from ..catalog import ValidationError


def amount(value=0):
    widget=AmountEdit(cents_text(value));widget.setPlaceholderText('0,00');widget.setMaximumWidth(220)
    return widget


def cents_text(value):
    return f'{value//100},{value%100:02d}'


class CalendarDateEdit(QDateEdit):
    """El clic en la fecha abre el calendario; el teclado sigue disponible."""
    def __init__(self, value, parent=None):
        super().__init__(value, parent)
        self.lineEdit().installEventFilter(self)
        self.lineEdit().setCursor(Qt.PointingHandCursor)
        self.setToolTip('Haz clic para elegir la fecha en el calendario')

    def eventFilter(self, watched, event):
        if watched is self.lineEdit() and event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            if event.button() == Qt.LeftButton:
                if event.type() == QEvent.MouseButtonRelease:
                    self.setFocus(Qt.MouseFocusReason)
                    option = QStyleOptionSpinBox()
                    self.initStyleOption(option)
                    arrow = self.style().subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxDown, self)
                    position = QPointF(arrow.center())
                    global_position = QPointF(self.mapToGlobal(arrow.center()))
                    # Use Qt's own popup so date limits, placement and selection stay native.
                    super().mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, position, global_position, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
                    super().mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, position, global_position, Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
                return True
        return super().eventFilter(watched, event)


def date_edit():
    widget=CalendarDateEdit(QDate.currentDate());widget.setCalendarPopup(True);widget.setDisplayFormat('dd/MM/yyyy');widget.setMaximumDate(QDate.currentDate())
    return widget


class AccountComboBox(QComboBox):
    about_to_open=Signal()

    def showPopup(self):
        self.about_to_open.emit()
        super().showPopup()


def account_combo(settings,selected=None):
    widget=AccountComboBox();widget.addItem('Selecciona una cuenta',None)
    for account in settings.list_accounts(): widget.addItem(account.name,account.id)
    if selected: widget.setCurrentIndex(max(0,widget.findData(selected)))
    return widget


def error_text(error):
    return '\n'.join(error.errors.values()) if isinstance(error,ValidationError) else str(error)


def note(text,name='muted'):
    w=QLabel(text);w.setWordWrap(True);w.setObjectName(name)
    from PySide6.QtCore import Qt
    w.setTextFormat(Qt.PlainText)
    return w


from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QCheckBox


class ToggleSwitch(QCheckBox):
    """Interruptor accesible con teclado, etiqueta y posición visible."""
    def sizeHint(self):
        return QSize(48+self.fontMetrics().horizontalAdvance(self.text()),28)

    def hitButton(self,pos):
        return self.rect().contains(pos)

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        y=(self.height()-20)/2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#315FDA' if self.isChecked() else '#8393ac'))
        painter.drawRoundedRect(QRectF(1,y,36,20),10,10)
        painter.setBrush(QColor('white'))
        painter.drawEllipse(QRectF(19 if self.isChecked() else 3,y+2,16,16))
        painter.setPen(QColor('#233047'))
        painter.drawText(self.rect().adjusted(46,0,0,0),Qt.AlignVCenter,self.text())
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#537BE3'),1,Qt.DotLine));painter.drawRoundedRect(self.rect().adjusted(0,0,-1,-1),4,4)


class AmountEdit(QLineEdit):
    """El primer clic al entrar selecciona el importe; el siguiente permite editarlo."""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._select_on_release = True
        if event.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason):
            self.selectAll()

    def mousePressEvent(self, event):
        entering = getattr(self, "_select_on_release", False) or not self.hasFocus()
        super().mousePressEvent(event)
        self._select_on_release = entering

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if getattr(self, '_select_on_release', False) and event.button() == Qt.LeftButton:
            self.selectAll()
            self._select_on_release = False


def shipping_method_combo():
    from ..sales import SHIPPING_PAYMENT_KINDS
    widget = QComboBox()
    for key, label in SHIPPING_PAYMENT_KINDS.items():
        widget.addItem(label, key)
    widget.setAccessibleName('Forma de pago del envío')
    widget.setToolTip('Forma utilizada para pagar a la transportadora. Crédito registra un cargo a la tarjeta; la cuenta es una referencia asociada.')
    return widget


def refresh_shipping_accounts(settings, combo, method):
    """Cards are payment sources, never sale receipt accounts."""
    selected=combo.currentData();combo.blockSignals(True);combo.clear();combo.addItem('Cuenta (opcional)',None)
    card_ids={r[0] for r in settings.connection.execute('SELECT account_id FROM credit_cards')}
    for account in settings.list_accounts(include_cards=True):
        is_card=account.id in card_ids
        control=settings.connection.execute('SELECT enabled FROM credit_card_settings WHERE id=1').fetchone()[0]
        if (method.currentData()=='credit_card')==is_card or (account.id==selected and not is_card) or (not control and not is_card):
            combo.addItem(account.name+(' · Crédito' if is_card else ''),account.id)
    combo.setCurrentIndex(max(0,combo.findData(selected)));combo.blockSignals(False)
