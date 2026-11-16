"""Editor de cargos y campos cambiarios reutilizables, sin guardar en SQLite."""
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView)
from .form_validation import check, required, amount_issue, choice
from ..purchases import CATEGORIES, PurchaseCostInput, validate_rate, convert_to_cop
from ..catalog import ValidationError
from ..sales import money
from .sales_widgets import AmountEdit, cents_text, date_edit, note, error_text
from .style import STYLE, format_cop


class CurrencyFields(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(6)
        row = QHBoxLayout(); row.addWidget(note('Moneda','fieldHeading'))
        self.currency = QComboBox(); self.currency.addItems(['COP','USD']); row.addWidget(self.currency)
        self.reference = QCheckBox('Registrar dólar de referencia · opcional'); row.addWidget(self.reference,1)
        root.addLayout(row)
        self.details = QWidget(); fields = QFormLayout(self.details); fields.setContentsMargins(0,0,0,0)
        self.rate = QLineEdit(); self.rate.setPlaceholderText('Ej. 4200,50 · hasta 6 decimales')
        self.converted_on = date_edit()
        fields.addRow('COP por USD',self.rate); fields.addRow('Fecha de conversión / referencia',self.converted_on)
        root.addWidget(self.details)
        self.currency.currentIndexChanged.connect(self._currency_changed)
        self.reference.toggled.connect(self._visibility)
        self.rate.textChanged.connect(lambda *_: self.changed.emit()); self.converted_on.dateChanged.connect(lambda *_: self.changed.emit())
        self._visibility()

    def _currency_changed(self):
        self.rate.clear(); self.reference.setChecked(False); self._visibility()

    def _visibility(self):
        usd = self.currency.currentText() == 'USD'
        self.reference.setVisible(not usd)
        self.details.setVisible(usd or self.reference.isChecked())
        self.changed.emit()

    def validation_issues(self):
        try:self.values()
        except ValidationError as error:return [(self.rate,error_text(error))]
        return []

    def values(self):
        currency = self.currency.currentText()
        if currency == 'COP' and not self.reference.isChecked():
            return currency, None, None
        try:
            rate = Decimal(self.rate.text().strip().replace(',','.'))
        except InvalidOperation:
            raise ValidationError({'tasa':'Escribe la tasa de cambio utilizada.'})
        validate_rate(rate)
        return currency, rate, self.converted_on.date().toPython()

    def set_values(self, currency, rate, converted_on):
        self.currency.setCurrentText(currency)
        self.reference.setChecked(currency == 'COP' and rate is not None)
        self.rate.setText(str(rate).replace('.',',') if rate is not None else '')
        if converted_on: self.converted_on.setDate(QDate(converted_on.year,converted_on.month,converted_on.day))
        self._visibility()


def table(headers):
    widget = QTableWidget(0,len(headers)); widget.setHorizontalHeaderLabels(headers)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    widget.verticalHeader().hide(); widget.verticalHeader().setDefaultSectionSize(40)
    widget.setSelectionBehavior(QTableWidget.SelectRows); widget.setSelectionMode(QTableWidget.SingleSelection)
    widget.setEditTriggers(QTableWidget.NoEditTriggers); widget.setMinimumHeight(120)
    return widget


class CostDialog(QDialog):
    def __init__(self, cost=None, parent=None,categories=None):
        super().__init__(parent); self.setWindowModality(Qt.WindowModal); self.setStyleSheet(STYLE)
        self.setWindowTitle('Costo de la compra'); self.resize(560,440); self.result_cost=None; self.validate_candidate=None; self.blocked_categories=set()
        root=QVBoxLayout(self); root.addWidget(note('Agregar o corregir un costo','cardTitle'))
        form=QFormLayout(); self.category=QComboBox()
        for key,name in (CATEGORIES if categories is None else categories).items(): self.category.addItem(name,key)
        self.amount=AmountEdit(); self.amount.setPlaceholderText('Importe original · ej. 42.500')
        self.description=QLineEdit(); self.description.setPlaceholderText('Dato adicional · ej. arancel UPS')
        self.description.setToolTip('Detalle opcional; obligatorio para «Otros costos».')
        form.addRow('Concepto',self.category)
        form.addRow('Importe',self.amount)
        form.addRow(note('Descripción adicional'),self.description)
        self.setTabOrder(self.category,self.amount)
        self.setTabOrder(self.amount,self.description)
        root.addLayout(form); self.exchange=CurrencyFields(); root.addWidget(self.exchange)
        root.addWidget(note('En COP se conserva el importe real; el dólar de referencia no lo reconvierte.'))
        self.error=note('','error'); root.addWidget(self.error)
        buttons=QHBoxLayout(); close=QPushButton('Cancelar'); add=QPushButton('Aplicar al formulario'); add.setObjectName('primary'); add.setDefault(True); close.setAutoDefault(False)
        buttons.addWidget(close); buttons.addWidget(add); root.addLayout(buttons)
        close.clicked.connect(self.reject); add.clicked.connect(self.apply)
        if cost:
            self.category.setCurrentIndex(self.category.findData(cost.category)); self.description.setText(cost.description)
            self.amount.setText(cents_text(cost.amount_cents)); self.exchange.set_values(cost.currency,cost.exchange_rate,cost.converted_on)

    def apply(self):
        issues=[choice(self.category,'el concepto del costo'),amount_issue(self.amount,'Importe del costo')]
        if self.category.currentData()=='other' and self.category.currentText()==CATEGORIES['other']:issues.append(required(self.description,'la descripción del costo'))
        issues.extend(self.exchange.validation_issues())
        if not check(self,issues,self.error):return
        try:
            currency,rate,converted_on=self.exchange.values()
            value=money(self.amount.text())
            if self.category.currentData()=='other' and self.category.currentText()==CATEGORIES['other'] and not self.description.text().strip():
                raise ValidationError({'concepto':'Describe este costo.'})
            convert_to_cop(value,currency,rate)
            self.result_cost=PurchaseCostInput(self.category.currentData(),self.description.text().strip(),value,currency,rate,converted_on)
            if self.validate_candidate:self.validate_candidate(self.result_cost)
            self.accept()
        except ValidationError as error: self.error.setText(error_text(error))


class PurchaseCostEditor(QWidget):
    changed=Signal()

    def __init__(self,parent=None,categories=None):
        self.categories=dict(CATEGORIES if categories is None else categories)
        super().__init__(parent); self._costs=[]; self.dialog=None; self.progress=None; self.state_combos={}; self.row_costs=[]; self.row_categories=[]; self.validate_candidate=None; self.blocked_categories=set()
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        self.description=note('Cada cargo conserva su importe original y su tasa de cambio.'); root.addWidget(self.description)
        self.table=table(['Concepto','Original','Costo · COP']); root.addWidget(self.table,1)
        row=QHBoxLayout()
        for title,callback in [('+ Agregar costo',lambda:self.open_editor()),('Editar',self.edit_selected),('Quitar',self.remove_selected)]:
            button=QPushButton(title); button.clicked.connect(callback); row.addWidget(button)
        root.addLayout(row); self.table.cellDoubleClicked.connect(self.edit_selected)

    def costs(self): return tuple(self._costs)

    def set_costs(self,costs):
        self._costs=list(costs); self.refresh()

    def bind_progress(self,progress):
        self.progress=progress
        self.description.hide()
        self.table.horizontalHeader().setFixedHeight(40)
        progress.changed.connect(self.sync_states)
        self.refresh()

    def sync_states(self):
        if self.progress is None: return
        states=self.progress.states()
        colors={'pending':'#fff1de','recorded':'#e9f6ee','not_applicable':'#edf0f5'}
        for key,combo in self.state_combos.items():
            combo.blockSignals(True)
            combo.setEnabled(True)
            combo.setToolTip("Selecciona el estado; se activará el seguimiento por concepto." if states is None else "")
            combo.setCurrentIndex(combo.findData(states[key] if states else 'pending'))
            combo.setStyleSheet('QComboBox { background: '+colors[combo.currentData()]+'; padding: 4px; }')
            combo.blockSignals(False)

    def refresh(self):
        self.table.setRowCount(0); self.state_combos={}; self.row_costs=[]; self.row_categories=[]
        self.table.setColumnCount(4 if self.progress else 3)
        self.table.setHorizontalHeaderLabels(['Concepto','Original','Costo · COP','Estado'] if self.progress else ['Concepto','Original','Costo · COP'])
        def append_row(key,index,values,with_state=False):
            row=self.table.rowCount(); self.table.insertRow(row)
            self.row_costs.append(index); self.row_categories.append(key)
            for col,value in enumerate(values):
                item=QTableWidgetItem(value.replace(' / ',' /\n') if col==0 else value); item.setToolTip(value); self.table.setItem(row,col,item)
            if with_state:
                combo=QComboBox()
                for label,value in [('Pendiente','pending'),('Registrado','recorded'),('No aplica','not_applicable')]: combo.addItem(label,value)
                combo.setAccessibleName('Estado de '+self.categories[key])
                self.state_combos[key]=combo; self.table.setCellWidget(row,3,combo)
                def changed(*args):
                    # Activation synchronizes every inline combo. Preserve the chosen
                    # value before that synchronization restores the legacy defaults.
                    selected=combo.currentData()
                    if self.progress.states() is None:
                        self.progress.activate.setChecked(True)
                    target=self.progress.editors[key]
                    target.setCurrentIndex(target.findData(selected))
                combo.currentIndexChanged.connect(changed)
                # Also handle explicitly choosing the already displayed Pending value.
                combo.activated.connect(changed)
            self.table.setRowHeight(row,52 if key=='importation' else 40)
        if self.progress:
            for key in self.categories:
                indices=[i for i,cost in enumerate(self._costs) if cost.category==key]
                if len(indices)==1:
                    i=indices[0]; cost=self._costs[i]
                    append_row(key,i,[self.categories[key],format_cop(cost.amount_cents)+' '+cost.currency,
                        format_cop(convert_to_cop(cost.amount_cents,cost.currency,cost.exchange_rate))],True)
                else:
                    total=sum(convert_to_cop(self._costs[i].amount_cents,self._costs[i].currency,self._costs[i].exchange_rate) for i in indices)
                    append_row(key,None,[self.categories[key],str(len(indices))+' cargos' if indices else 'Sin cargos',format_cop(total)],True)
                    for i in indices:
                        cost=self._costs[i]
                        append_row(key,i,['  '+(cost.description or 'Cargo'),format_cop(cost.amount_cents)+' '+cost.currency,
                            format_cop(convert_to_cop(cost.amount_cents,cost.currency,cost.exchange_rate))])
            self.sync_states()
        else:
            for i,cost in enumerate(self._costs):
                append_row(cost.category,i,[self.categories[cost.category],format_cop(cost.amount_cents)+' '+cost.currency,
                    format_cop(convert_to_cop(cost.amount_cents,cost.currency,cost.exchange_rate))])
        self.changed.emit()

    def edit_selected(self,*args):
        row=self.table.currentRow()
        if 0<=row<len(self.row_costs):
            self.open_editor(self.row_costs[row])
            if self.row_costs[row] is None:
                self.dialog.category.setCurrentIndex(self.dialog.category.findData(self.row_categories[row]))

    def remove_selected(self):
        row=self.table.currentRow()
        if 0<=row<len(self.row_costs) and self.row_costs[row] is not None:
            self._costs.pop(self.row_costs[row]); self.refresh()

    def open_editor(self,index=None):
        if self.dialog and self.dialog.isVisible(): self.dialog.raise_(); return
        self.dialog=CostDialog(self._costs[index] if index is not None else None,self,categories=self.categories)
        dialog=self.dialog
        if self.blocked_categories:
            for i in range(dialog.category.count()):
                if dialog.category.itemData(i) in self.blocked_categories:
                    dialog.category.model().item(i).setEnabled(False)
            if dialog.category.currentData() in self.blocked_categories:dialog.category.setCurrentIndex(-1)
            dialog.error.setText('IVA ya calculado en productos. No puedes agregarlo también como costo de factura.')
        dialog.validate_candidate=lambda cost: self.validate_candidate(cost,index) if self.validate_candidate else None
        def applied():
            if index is None: self._costs.append(dialog.result_cost)
            else: self._costs[index]=dialog.result_cost
            self.refresh()
        dialog.accepted.connect(applied); dialog.show()
