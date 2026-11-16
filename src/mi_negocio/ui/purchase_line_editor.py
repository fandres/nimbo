from .numeric_spinbox import NumericSpinBox as QSpinBox
"""Edición de una línea de mercancía antes de guardar el pedido."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup,QCompleter,QDialog,QVBoxLayout,QFormLayout,QComboBox,QPushButton,QHBoxLayout
from .vat_fields import VatFields
from .preferences import DisplayPreferences
from ..vat import split_vat
from .completion import enable_unique_tab
from .form_validation import check, amount_issue
from ..purchases import PurchaseLineInput, convert_to_cop, line_original_total, line_entered_total
from decimal import Decimal, ROUND_HALF_UP
from ..sales import money
from ..purchase_allocation import ALLOCATION_FIELDS
from ..catalog import ValidationError
from .purchase_cost_editor import CurrencyFields
from .sales_widgets import AmountEdit, cents_text, note, error_text
from .style import STYLE


class PurchaseLineDialog(QDialog):
    def __init__(self, products, line=None, historical_name='', parent=None,preferences=None):
        super().__init__(parent); self.setStyleSheet(STYLE); self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle('Producto comprado'); self.resize(680,390); self.result_line=None; self.original=line; self.validate_candidate=None
        root=QVBoxLayout(self); root.addWidget(note('Qué compramos','cardTitle'))
        form=QFormLayout(); self.product=QComboBox(); self.product.setEditable(True)
        self.product.setInsertPolicy(QComboBox.NoInsert)
        for p in products: self.product.addItem(p.code+' · '+p.name,p.id)
        if line and self.product.findData(line.product_id)<0:
            self.product.addItem(historical_name,line.product_id)
        self.product.setCurrentIndex(-1); self.product.lineEdit().setPlaceholderText('Buscar por código o nombre…')
        self.product.completer().setFilterMode(Qt.MatchContains); self.product.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.product.completer().setCompletionMode(QCompleter.PopupCompletion)
        enable_unique_tab(self.product)
        self.quantity=QSpinBox(); self.quantity.setRange(1,1000000000)
        self.amount=AmountEdit(); self.amount.setPlaceholderText('Costo de compra'); self.amount.setFixedWidth(240)
        self.cost_mode=QButtonGroup(self)
        self.total_mode=QPushButton('Total'); self.unit_mode=QPushButton('Por unidad')
        modes=QHBoxLayout(); modes.setSpacing(0)
        for button in (self.total_mode,self.unit_mode):
            button.setCheckable(True); button.setAutoDefault(False)
            button.setObjectName('paymentChoice'); self.cost_mode.addButton(button)
            modes.addWidget(button)
        self.total_mode.setToolTip('Costo total de todas estas unidades')
        self.unit_mode.setToolTip('Costo de una sola unidad')
        self.total_mode.setChecked(True)
        self.amount_label=note('Costo total')
        self.amount_label.setFixedWidth(self.amount_label.fontMetrics().horizontalAdvance('Costo por unidad')+8)
        self.amount_label.setWordWrap(False)
        self.cost_preview=note('Ingresa el costo de todas las unidades de este producto.')
        self._switching=False; self._exact_total=None; self._mode='total'
        form.addRow('Producto',self.product); form.addRow('Cantidad',self.quantity)
        cost_row=QHBoxLayout(); cost_row.addWidget(self.amount); cost_row.addLayout(modes); cost_row.addStretch(1)
        form.addRow(self.amount_label,cost_row)
        form.addRow(self.cost_preview)
        root.addLayout(form)
        preferences=preferences or DisplayPreferences()
        self.vat=VatFields(preferences.vat_default('purchases'));root.addWidget(self.vat)
        self.vat_preview=note('');root.addWidget(self.vat_preview)
        self.exchange=CurrencyFields(); root.addWidget(self.exchange)
        root.addWidget(note('Agrega envío, impuestos y otros cargos en 3 · Costos adicionales del pedido.'))
        self.error=note('','error'); root.addWidget(self.error)
        buttons=QHBoxLayout(); cancel=QPushButton('Cancelar'); apply=QPushButton('Aplicar al formulario'); apply.setObjectName('primary'); apply.setDefault(True); cancel.setAutoDefault(False)
        buttons.addWidget(cancel); buttons.addWidget(apply); root.addLayout(buttons)
        cancel.clicked.connect(self.reject); apply.clicked.connect(self.accept_line)
        if line:
            self.product.setCurrentIndex(self.product.findData(line.product_id)); self.product.setEnabled(line.line_id is None)
            self.quantity.setValue(line.quantity); self.amount.setText(cents_text(line_entered_total(line)))
            self.exchange.set_values(line.currency,line.exchange_rate,line.converted_on)
            self.vat.set_values(line.vat_enabled,line.vat_rate,line.vat_included)

        self.cost_mode.buttonClicked.connect(self.switch_cost_mode)
        self.amount.textChanged.connect(self.cost_changed)
        self.quantity.valueChanged.connect(self.cost_changed)
        self.exchange.changed.connect(self.update_preview)
        self.vat.changed.connect(self.update_preview)
        self.cost_changed()

    def cost_changed(self, *_):
        if self._switching:return
        try:self._exact_total=money(self.amount.text()) if self._mode=='total' else None
        except ValidationError:self._exact_total=None
        self.update_preview()

    def original_total(self):
        value=money(self.amount.text())
        return self._exact_total if self._exact_total is not None else value*self.quantity.value()

    def switch_cost_mode(self):
        new_mode='total' if self.total_mode.isChecked() else 'unit'
        if new_mode==self._mode:return
        try:
            total=self.original_total()
            value=total if new_mode=='total' else int((Decimal(total)/self.quantity.value()).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            self._switching=True
            self.amount.setText(cents_text(value));self._exact_total=total
        except ValidationError:
            self._exact_total=None
        finally:self._switching=False
        self._mode=new_mode
        self.amount_label.setText('Costo total' if new_mode=='total' else 'Costo por unidad')
        self.update_preview()

    def update_preview(self):
        try:
            total=self.original_total();quantity=self.quantity.value()
            unit=int((Decimal(total)/quantity).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            currency=self.exchange.currency.currentText()
            values=self.vat.values();base,vat,gross=split_vat(total,values['vat_enabled'],values['vat_rate'],values['vat_included'])
            self.vat_preview.setVisible(values['vat_enabled'])
            self.vat_preview.setText(f'Base: {cents_text(base)} · IVA: {cents_text(vat)} · Total: {cents_text(gross)} {currency}')
            prefix='≈ ' if total % quantity else ''
            complement=(f'Costo por unidad: {prefix}{cents_text(unit)} {currency}'
                        if self._mode=='total' else f'Costo total: {cents_text(total)} {currency}')
            self.cost_preview.setText(complement+'\nSolo mercancía de este producto; gastos adicionales separados.')
        except ValidationError:
            self.vat_preview.setText('Revisa el importe y el porcentaje de IVA.')
            self.cost_preview.setText('Ingresa el costo de la mercancía, sin los gastos adicionales.')

    def accept_line(self):
        issues=[amount_issue(self.amount,self.amount_label.text())]
        if self.product.findText(self.product.currentText())<0:issues.insert(0,(self.product,'Selecciona un producto de los resultados.'))
        issues.extend(self.exchange.validation_issues());issues.extend(self.vat.issues())
        if not check(self,issues,self.error):return
        try:
            index=self.product.findText(self.product.currentText())
            if index<0: raise ValidationError({'producto':'Selecciona un producto de los resultados.'})
            currency,rate,converted_on=self.exchange.values(); value=money(self.amount.text())
            total=self.original_total()
            convert_to_cop(total,currency,rate)
            value=int((Decimal(total)/self.quantity.value()).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            self.result_line=PurchaseLineInput(self.product.itemData(index),self.quantity.value(),value,currency,rate,converted_on,
                                               self.original.line_id if self.original else None,
                                               **self.vat.values(),total_cost_cents=total, extra_allocations=dict(self.original.extra_allocations) if self.original else {}, **{field:getattr(self.original,field,0) for field in ALLOCATION_FIELDS.values()})
            if self.validate_candidate:self.validate_candidate(self.result_line)
            self.accept()
        except ValidationError as error: self.error.setText(error_text(error))
