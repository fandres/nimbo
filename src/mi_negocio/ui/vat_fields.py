"""Control compacto y compartido para importes con o sin IVA."""
from decimal import Decimal
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QPushButton,QButtonGroup
from .sales_widgets import ToggleSwitch,AmountEdit,note
from .form_validation import rate_issue
from ..catalog import ValidationError


class VatFields(QWidget):
    changed=Signal()
    def __init__(self,enabled=False,parent=None):
        super().__init__(parent)
        root=QHBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(8)
        root.addWidget(note('Aplicar IVA'))
        self.enabled=ToggleSwitch('');self.enabled.setAccessibleName('Aplicar IVA');root.addWidget(self.enabled)
        self.fields=QWidget();row=QHBoxLayout(self.fields);row.setContentsMargins(0,0,0,0);row.setSpacing(4)
        self.rate=AmountEdit('19');self.rate.setMaximumWidth(76);self.rate.setAccessibleName('Porcentaje de IVA');row.addWidget(self.rate);row.addWidget(note('%'))
        self.excluded=QPushButton('Sin IVA');self.included=QPushButton('IVA incluido');self.group=QButtonGroup(self)
        for button in (self.excluded,self.included):
            button.setCheckable(True);button.setAutoDefault(False);button.setObjectName('paymentChoice');self.group.addButton(button);row.addWidget(button)
        self.excluded.setToolTip('El importe ingresado es la base: se suma el IVA.')
        self.included.setToolTip('El importe ingresado ya contiene IVA: se desglosa sin sumarlo otra vez.')
        self.excluded.setChecked(True);root.addWidget(self.fields);root.addStretch()
        self.enabled.setChecked(enabled);self.fields.setVisible(enabled)
        self.enabled.toggled.connect(self.fields.setVisible);self.enabled.toggled.connect(lambda *_:self.changed.emit())
        self.rate.textChanged.connect(lambda *_:self.changed.emit());self.group.buttonClicked.connect(lambda *_:self.changed.emit())

    def values(self):
        if not self.enabled.isChecked():
            return dict(vat_enabled=False,vat_rate=Decimal('19'),vat_included=False)
        issue=rate_issue(self.rate,'IVA',100)
        if issue:raise ValidationError({'iva':issue[1]})
        return dict(vat_enabled=self.enabled.isChecked(),vat_rate=Decimal(self.rate.text().replace(',','.')),vat_included=self.included.isChecked())

    def issues(self):
        return [rate_issue(self.rate,'IVA',100)] if self.enabled.isChecked() else []

    def set_values(self,enabled,rate,included):
        self.rate.setText(str(rate));self.enabled.setChecked(enabled)
        (self.included if included else self.excluded).setChecked(True)
