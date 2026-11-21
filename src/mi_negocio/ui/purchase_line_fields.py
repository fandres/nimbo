"""Controles de la ficha de mercancía; conservan las interfaces de IVA y moneda."""
from decimal import Decimal
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QButtonGroup, QPushButton, QCheckBox, QComboBox, QLineEdit
from .vat_fields import VatFields
from .purchase_cost_editor import CurrencyFields
from .sales_widgets import AmountEdit, note, date_edit


def choice_button(text, group, layout):
    button=QPushButton(text);button.setCheckable(True);button.setAutoDefault(False)
    button.setObjectName('paymentChoice');group.addButton(button);layout.addWidget(button)
    return button


class PurchaseVatFields(VatFields):
    def __init__(self, enabled=False, parent=None):
        QWidget.__init__(self,parent)
        self._syncing=False
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(8)
        root.addWidget(note('IVA','fieldHeading'))
        self.enabled=QCheckBox(self);self.enabled.hide();self.enabled.installEventFilter(self)
        row=QHBoxLayout();row.setSpacing(6);self.group=QButtonGroup(self)
        self.no_vat=choice_button('No aplica',self.group,row)
        self.excluded=choice_button('Sumar IVA al costo',self.group,row)
        self.included=choice_button('IVA ya incluido',self.group,row)
        root.addLayout(row)
        self.fields=QWidget();rates=QHBoxLayout(self.fields);rates.setContentsMargins(0,0,0,0);rates.setSpacing(6)
        rates.addWidget(note('Tarifa'));self.rates=QButtonGroup(self)
        self.rate_19=choice_button('19 %',self.rates,rates)
        self.rate_5=choice_button('5 %',self.rates,rates)
        self.other_rate=choice_button('Otra',self.rates,rates)
        self.rate=AmountEdit('19');self.rate.setMaximumWidth(95);self.rate.setAccessibleName('Porcentaje de IVA')
        rates.addWidget(self.rate);self.hint=note('');rates.addWidget(self.hint,1)
        root.addWidget(self.fields)
        self.group.buttonClicked.connect(self._mode_changed)
        self.enabled.toggled.connect(self._enabled_changed)
        self.rates.buttonClicked.connect(self._rate_choice)
        self.rate.textChanged.connect(self._rate_changed)
        self.set_values(enabled,Decimal('19'),False)

    def eventFilter(self, obj, event):
        if obj is self.enabled and event.type()==QEvent.EnabledChange:
            for button in (self.excluded,self.included):button.setEnabled(self.enabled.isEnabled())
        if obj is self.enabled and event.type()==QEvent.ToolTipChange:
            for button in (self.excluded,self.included):button.setToolTip(self.enabled.toolTip())
        return super().eventFilter(obj,event)

    def _mode_changed(self):
        self._syncing=True;self.enabled.setChecked(not self.no_vat.isChecked());self._syncing=False
        self._refresh();self.changed.emit()

    def _enabled_changed(self, enabled):
        if self._syncing:return
        if not enabled:self.no_vat.setChecked(True)
        elif self.no_vat.isChecked():self.excluded.setChecked(True)
        self._refresh();self.changed.emit()

    def _refresh(self):
        self.fields.setVisible(self.enabled.isChecked())
        self.rate.setVisible(self.other_rate.isChecked())
        self.hint.setText('El costo ya contiene IVA; se separa del total.' if self.included.isChecked()
                          else 'El costo no incluye IVA; se suma al total.')

    def _rate_choice(self):
        if self.rate_19.isChecked():self.rate.setText('19')
        elif self.rate_5.isChecked():self.rate.setText('5')
        self._refresh();self.changed.emit()
        if self.other_rate.isChecked():self.rate.setFocus();self.rate.selectAll()

    def _rate_changed(self):
        # Do not hide the custom editor when typing a prefix such as 5 in 5,5.
        self._refresh();self.changed.emit()

    def set_values(self, enabled, rate, included):
        self._syncing=True
        self.enabled.setChecked(enabled)
        (self.no_vat if not enabled else self.included if included else self.excluded).setChecked(True)
        self.rate.setText(str(rate).replace('.',','))
        (self.rate_19 if rate==19 else self.rate_5 if rate==5 else self.other_rate).setChecked(True)
        self._syncing=False;self._rate_changed()


class PurchaseCurrencyFields(CurrencyFields):
    def __init__(self, parent=None):
        QWidget.__init__(self,parent)
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(6)
        self.currency=QComboBox(self);self.currency.addItems(['COP','USD']);self.currency.hide()
        self.reference=QCheckBox('Registrar dólar de referencia · opcional');root.addWidget(self.reference)
        self.details=QWidget();self.details.setObjectName('exchangeCard')
        fields=QVBoxLayout(self.details);fields.setContentsMargins(12,8,12,8)
        fields.addWidget(note('Tasa de cambio · COP por 1 USD','fieldHeading'))
        row=QHBoxLayout()
        self.rate=QLineEdit();self.rate.setPlaceholderText('Ej. 4100,50');self.rate.setMaximumWidth(170)
        self.rate.setAlignment(Qt.AlignRight);row.addWidget(self.rate)
        self.converted_on=date_edit();self.converted_on.setMaximumWidth(150)
        row.addStretch();row.addWidget(note('Fecha de conversión'));row.addWidget(self.converted_on)
        fields.addLayout(row);self.conversion=note('');fields.addWidget(self.conversion)
        root.addWidget(self.details)
        self.currency.currentIndexChanged.connect(self._currency_changed)
        self.reference.toggled.connect(self._visibility)
        self.rate.textChanged.connect(lambda *_:self.changed.emit())
        self.converted_on.dateChanged.connect(lambda *_:self.changed.emit())
        self._visibility()
