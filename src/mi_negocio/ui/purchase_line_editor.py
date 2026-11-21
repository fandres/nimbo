from PySide6.QtWidgets import QSpinBox
"""Edición de una línea de mercancía antes de guardar el pedido."""
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QButtonGroup,QCompleter,QDialog,QVBoxLayout,QGridLayout,QFrame,QComboBox,QPushButton,QHBoxLayout,QWidget
from .purchase_line_fields import PurchaseVatFields, PurchaseCurrencyFields, choice_button
from .preferences import DisplayPreferences
from ..vat import split_vat
from .completion import enable_unique_tab
from .form_validation import check, amount_issue
from ..purchases import PurchaseLineInput, convert_to_cop, line_entered_total
from decimal import Decimal, ROUND_HALF_UP
from ..sales import money
from ..purchase_allocation import ALLOCATION_FIELDS
from ..catalog import ValidationError
from .sales_widgets import AmountEdit, cents_text, note, error_text
from .style import STYLE, format_cop


class PurchaseLineDialog(QDialog):
    def __init__(self, products, line=None, historical_name='', parent=None,preferences=None):
        super().__init__(parent); self.setStyleSheet(STYLE); self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle('Producto comprado'); self.resize(820,760); self.result_line=None; self.original=line; self.validate_candidate=None
        self.setStyleSheet(STYLE+"""
        QWidget#exchangeCard { background: #f7f9fd; border: 1px solid #e2e8f2; border-radius: 10px; }
        QFrame#purchaseSummary { background: white; border: 1px solid #e2e8f2; border-radius: 12px; }
        QLabel#purchaseTotal { color: #142b50; font-size: 22px; font-weight: 700; }
        QPushButton#paymentChoice { padding: 8px 10px; }
        QPushButton#quantityStep { padding: 0; color: #315fda; font-size: 18px; min-height: 34px; }
        QSpinBox#purchaseQuantity { padding: 5px 2px; min-height: 26px; }
        QSpinBox#purchaseQuantity::up-button, QSpinBox#purchaseQuantity::down-button { width: 0; height: 0; }
        """)
        root=QVBoxLayout(self);root.setContentsMargins(24,20,24,16);root.setSpacing(8)
        root.addWidget(note('Qué compramos','cardTitle'))
        root.addWidget(note('Producto','fieldHeading'))
        self.product=QComboBox();self.product.setEditable(True)
        self.product.setInsertPolicy(QComboBox.NoInsert)
        for p in products:self.product.addItem(p.code+' · '+p.name,p.id)
        if line and self.product.findData(line.product_id)<0:self.product.addItem(historical_name,line.product_id)
        self.product.setCurrentIndex(-1);self.product.lineEdit().setPlaceholderText('Buscar por código o nombre…')
        self.product.completer().setFilterMode(Qt.MatchContains);self.product.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.product.completer().setCompletionMode(QCompleter.PopupCompletion);enable_unique_tab(self.product)
        root.addWidget(self.product)
        grid=QGridLayout();grid.setHorizontalSpacing(14);grid.setVerticalSpacing(6)
        grid.addWidget(note('Cantidad','fieldHeading'),0,0)
        self.amount_label=note('Costo','fieldHeading');grid.addWidget(self.amount_label,0,1)
        self.cost_mode=QButtonGroup(self);modes=QHBoxLayout();modes.setSpacing(0)
        self.total_mode=choice_button('Total de la compra',self.cost_mode,modes)
        self.unit_mode=choice_button('Por unidad',self.cost_mode,modes)
        self.total_mode.setToolTip('Total de todas las unidades de este producto')
        self.total_mode.setChecked(True);grid.addLayout(modes,0,2)
        quantity_row=QHBoxLayout();quantity_row.setSpacing(0)
        self.decrease=QPushButton('−');self.increase=QPushButton('+')
        self.quantity=QSpinBox();self.quantity.setRange(1,1000000000)
        self.quantity.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows);self.quantity.setAlignment(Qt.AlignCenter)
        self.quantity.setObjectName('purchaseQuantity');self.quantity.setAccessibleName('Cantidad');self.quantity.setMinimumWidth(80)
        for button in (self.decrease,self.increase):button.setAutoDefault(False);button.setFixedWidth(32);button.setObjectName('quantityStep')
        self.decrease.setAccessibleName('Disminuir cantidad');self.increase.setAccessibleName('Aumentar cantidad')
        self.decrease.clicked.connect(lambda:self.quantity.stepDown() if self.quantity.isEnabled() else None)
        self.increase.clicked.connect(lambda:self.quantity.stepUp() if self.quantity.isEnabled() else None)
        quantity_row.addWidget(self.decrease);quantity_row.addWidget(self.quantity);quantity_row.addWidget(self.increase)
        quantity_box=QWidget();quantity_box.setLayout(quantity_row);quantity_box.setMaximumWidth(170)
        quantity_row.setContentsMargins(0,0,0,0);grid.addWidget(quantity_box,1,0)
        cost_row=QHBoxLayout();cost_row.setSpacing(6)
        self.currencies=QButtonGroup(self)
        self.cop_button=choice_button('COP',self.currencies,cost_row)
        self.usd_button=choice_button('USD',self.currencies,cost_row)
        self.cop_button.setChecked(True)
        self.amount=AmountEdit();self.amount.setPlaceholderText('Costo de compra');self.amount.setAlignment(Qt.AlignRight)
        cost_row.addWidget(self.amount,1);grid.addLayout(cost_row,1,1,1,2)
        self.cost_preview=note('Ingresa el costo de todas las unidades de este producto.')
        grid.addWidget(self.cost_preview,2,1,1,2)
        self.exchange=PurchaseCurrencyFields();grid.addWidget(self.exchange,3,1,1,2)
        grid.setColumnStretch(1,1);grid.setColumnStretch(2,1);root.addLayout(grid)
        preferences=preferences or DisplayPreferences()
        self.vat=PurchaseVatFields(preferences.vat_default('purchases'));self.vat.set_values(preferences.vat_default('purchases'),preferences.purchase_vat_rate(),False);root.addWidget(self.vat)
        summary=QFrame();summary.setObjectName('purchaseSummary');summary_layout=QVBoxLayout(summary)
        summary_layout.setContentsMargins(18,14,18,14);summary_layout.setSpacing(8)
        self.base_summary=note('—');self.vat_summary=note('—');self.total_summary=note('—','purchaseTotal')
        self.vat_caption=note('IVA')
        for label,value in ((note('Base (mercancía)'),self.base_summary),(self.vat_caption,self.vat_summary)):
            row=QHBoxLayout();row.addWidget(label);row.addStretch();row.addWidget(value);summary_layout.addLayout(row)
        rule=QFrame();rule.setFrameShape(QFrame.HLine);summary_layout.addWidget(rule)
        row=QHBoxLayout();row.addWidget(note('Total a pagar','fieldHeading'));row.addStretch();row.addWidget(self.total_summary);summary_layout.addLayout(row)
        self.vat_preview=note('');summary_layout.addWidget(self.vat_preview);root.addWidget(summary)
        root.addWidget(note('Solo mercancía de este producto. Envío, impuestos y otros cargos se agregan en el paso 3 · Costos adicionales del pedido.'))
        self._switching=False;self._exact_total=None;self._mode='total'
        self.currencies.buttonClicked.connect(lambda:self.exchange.currency.setCurrentText('USD' if self.usd_button.isChecked() else 'COP'))
        self.exchange.currency.currentTextChanged.connect(lambda currency:(self.usd_button if currency=='USD' else self.cop_button).setChecked(True))
        root.addStretch(1)
        self.error=note('','error'); root.addWidget(self.error)
        buttons=QHBoxLayout(); cancel=QPushButton('Cancelar'); apply=QPushButton('Aplicar al formulario'); apply.setObjectName('primary'); apply.setDefault(True); cancel.setAutoDefault(False)
        buttons.addWidget(cancel,1); buttons.addWidget(apply,2); root.addLayout(buttons)
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
        self.setTabOrder(self.product,self.quantity)
        self.setTabOrder(self.quantity,self.amount)
        self.setTabOrder(self.amount,self.total_mode)
        self.setTabOrder(self.total_mode,self.unit_mode)
        self.quantity.installEventFilter(self)
        self.quantity.valueChanged.connect(self._quantity_controls)
        self._quantity_controls()
        self.cost_changed()

    def _quantity_controls(self, *_):
        self.decrease.setEnabled(self.quantity.isEnabled() and self.quantity.value()>self.quantity.minimum())
        self.increase.setEnabled(self.quantity.isEnabled() and self.quantity.value()<self.quantity.maximum())

    def eventFilter(self, obj, event):
        if obj is self.quantity and event.type()==QEvent.EnabledChange:self._quantity_controls()
        return super().eventFilter(obj,event)

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
        self.amount.setAccessibleName('Costo total' if new_mode=='total' else 'Costo por unidad')
        self.update_preview()

    def update_preview(self):
        try:
            total=self.original_total();quantity=self.quantity.value()
            unit=int((Decimal(total)/quantity).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            currency,rate,_=self.exchange.values()
            values=self.vat.values();base,vat,gross=split_vat(total,values['vat_enabled'],values['vat_rate'],values['vat_included'])
            base_cop=convert_to_cop(base,currency,rate)
            # Same order of conversion and rounding as persistence, including fractional USD cents.
            entered_cop=convert_to_cop(total,currency,rate)
            vat_cop=convert_to_cop(gross,currency,rate)-base_cop
            gross_cop=base_cop+vat_cop
            self.base_summary.setText(format_cop(base_cop));self.vat_summary.setText(format_cop(vat_cop))
            self.total_summary.setText(format_cop(gross_cop)+' COP')
            self.vat_caption.setText('IVA '+str(values['vat_rate']).replace('.',',')+' %' if values['vat_enabled'] else 'IVA · No aplica')
            prefix='≈ ' if total % quantity else ''
            def original_money(value):return ('US$ ' if currency=='USD' else '$ ')+format_cop(value).split('$ ',1)[1]
            self.cost_preview.setText(('= '+prefix+original_money(unit)+' por unidad') if self._mode=='total' else '= '+original_money(total)+' en total')
            base_unit=int((Decimal(base_cop)/quantity).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            self.vat_preview.setText('Costo por unidad sin IVA: '+('≈ ' if base_cop%quantity else '')+format_cop(base_unit)+' COP')
            self.exchange.conversion.setText(('Mercancía ingresada: ' if currency=='USD' else 'Importe en COP (la referencia no lo convierte): ')+format_cop(entered_cop)+' COP')
        except ValidationError:
            for label in (self.base_summary,self.vat_summary,self.total_summary):label.setText('—')
            self.vat_preview.setText('Completa el costo, la tasa de cambio y el IVA para ver el desglose.')
            self.cost_preview.setText('Ingresa el costo de la mercancía, sin los gastos adicionales.')
            self.exchange.conversion.setText('')

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
