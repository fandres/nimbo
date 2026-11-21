"""Formulario de compra: cabecera, mercancía, cargos y resumen agrupado."""
from .attachments_dialog import attachment_button
from .completion import enable_unique_tab
from datetime import date
from dataclasses import replace
import json
from ..purchase_concepts import PurchaseConceptsRepository
from ..purchase_cost_rules import PurchaseCostRules
from ..purchases import categories_for, check_duplicate_vat, is_vat_cost, cost_states_complete
from decimal import Decimal
from uuid import uuid4
from PySide6.QtCore import Qt, Signal, QDate, QSignalBlocker
from PySide6.QtWidgets import (QDialog, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QComboBox, QPushButton, QScrollArea, QCompleter, QTableWidgetItem,
    QMessageBox, QInputDialog, QTextEdit)
from .form_validation import required_reason, check, required, rate_issue
from .preferences import DisplayPreferences
from .sales_widgets import ToggleSwitch, AmountEdit
from ..purchases import apply_invoice_vat, line_base_cop
from ..purchases import (PurchaseDraft, PurchaseLineInput, PurchaseCostInput,
                        calculate_purchase_totals, convert_to_cop, preview_purchase_totals, line_original_total)
from ..storage import StorageError
from ..purchase_receipts_repository import PurchaseReceiptsRepository
from ..purchases import CATEGORIES
from ..purchase_allocation import ALLOCATION_FIELDS, allocation_summary, line_unit_costs, automatic_allocations
from .purchase_progress_editor import PurchaseProgressEditor
from ..catalog import ValidationError
from .sales_widgets import date_edit, note, error_text
from .style import STYLE, format_cop
from .purchase_cost_editor import PurchaseCostEditor, table
from .purchase_line_editor import PurchaseLineDialog


def section(title):
    frame=QFrame(); frame.setObjectName('saleSection')
    layout=QVBoxLayout(frame); layout.setContentsMargins(12,8,12,8); layout.setSpacing(6)
    layout.addWidget(note(title,'cardTitle'))
    return frame,layout


class PurchaseDialog(QDialog):
    saved=Signal(int)

    def __init__(self,catalog,purchases,parent=None,purchase_id=None):
        super().__init__(parent)
        self.catalog=catalog; self.purchases=purchases; self.purchase_id=purchase_id
        self.cost_definitions=PurchaseConceptsRepository(catalog.connection).definitions()
        if purchase_id:
            self.cost_definitions=purchases.get(purchase_id)['cost_definitions']
        self.categories={key:value['name'] for key,value in self.cost_definitions.items()}
        self.product_names={p.id:p.code+' · '+p.name for p in catalog.list_products()}
        self.request_id=uuid4().hex; self.revision=1; self.lines=[]; self.names={}; self.line_dialog=None
        self.setWindowModality(Qt.WindowModal); self.setStyleSheet(STYLE)
        self.setWindowTitle('Compra · Nimbo' if purchase_id else 'Nueva compra · Nimbo')
        self.setMinimumSize(720,520)
        available=self.screen().availableGeometry(); self.resize(min(1440,available.width()-24),min(900,available.height()-48))
        root=QVBoxLayout(self); root.setContentsMargins(16,12,16,12); root.setSpacing(6)
        root.addWidget(note('Compra #'+str(purchase_id) if purchase_id else 'Nueva compra','heading'))
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.body=QWidget(); self.body.setObjectName('saleBody'); body=QVBoxLayout(self.body); body.setContentsMargins(0,0,0,0)
        self.scroll.setWidget(self.body); root.addWidget(self.scroll,1)
        self.header,header=section('1 · Proveedor y fecha')
        fields=QGridLayout(); self.supplier=QLineEdit(); self.supplier.setPlaceholderText('Proveedor · obligatorio')
        self.supplier_alias=QLineEdit();self.supplier_alias.setMaxLength(100);self.supplier_alias.setPlaceholderText('Ej. AlgoLaser · opcional')
        suppliers=self.purchases.supplier_suggestions()
        known={value.casefold() for name,alias in suppliers for value in (name,alias) if value}
        suppliers.extend((name,'') for name in self.catalog.list_options('brand') if name.casefold() not in known)
        self.supplier_suggestions={((alias+' · '+name) if alias else name):(name,alias)
                                   for name,alias in sorted(suppliers,key=lambda pair:(pair[1] or pair[0]).casefold())}
        self.supplier.setPlaceholderText('Escribe para buscar un proveedor o agregar uno nuevo')
        for field in (self.supplier,self.supplier_alias):
            completer=QCompleter(list(self.supplier_suggestions),field)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setCaseSensitivity(Qt.CaseInsensitive);completer.setFilterMode(Qt.MatchContains)
            # Normalize after Qt has inserted the completion label into the editor.
            # Windows otherwise overwrites the canonical name with "alias · name".
            field.setCompleter(completer)
            completer.activated[str].connect(self.select_supplier, Qt.QueuedConnection)
            enable_unique_tab(field)

        self.purchased_on=date_edit(); self.reference=QLineEdit(); self.reference.setPlaceholderText('Factura o pedido · opcional')
        fields.addWidget(note('Proveedor','fieldHeading'),0,0)
        fields.addWidget(self.supplier,1,0)
        fields.addWidget(note('Alias del proveedor · opcional','fieldHeading'),0,1)
        fields.addWidget(self.supplier_alias,1,1)
        fields.addWidget(note('Fecha de compra','fieldHeading'),0,2);fields.addWidget(self.purchased_on,1,2)
        fields.addWidget(note('Factura / pedido','fieldHeading'),0,3);fields.addWidget(self.reference,1,3)
        self.tracking=QLineEdit();self.tracking.setMaxLength(200)
        self.tracking.setPlaceholderText('Número de guía o tracking · opcional')
        fields.addWidget(note('Guía / tracking · opcional'),0,4)
        fields.addWidget(self.tracking,1,4)
        fields.setColumnStretch(4,2)
        fields.setColumnStretch(0,3);fields.setColumnStretch(1,2);fields.setColumnStretch(3,2);header.addLayout(fields); body.addWidget(self.header)
        self.grid=QGridLayout(); self.grid.setSpacing(12); body.addLayout(self.grid,1); self._compact=None
        self.products_panel,products=section('2 · Qué compramos')
        self.products_panel.setToolTip('Costos de compra y cantidades; todavía no son existencias disponibles.')
        self.lines_table=table(['Producto','Cant.','Compra/u\nCOP','Con gastos\npor unidad\nCOP','Total\nmercancía\nCOP']); products.addWidget(self.lines_table,1)
        self.products_total=note('Total de productos: $ 0,00','summaryAmount')
        self.products_total.setStyleSheet('background: #eaf0ff; color: #162e50; padding: 10px; border-radius: 10px; font-weight: 700;')
        self.products_total.setToolTip('Suma de la mercancía agregada al formulario, sin gastos adicionales. No requiere guardar.')
        products.addWidget(self.products_total)
        iva_row=QHBoxLayout()
        self.invoice_vat_enabled=ToggleSwitch('')
        self.invoice_vat_enabled.setAccessibleName('Separar IVA del total')
        iva_row.addWidget(self.invoice_vat_enabled)
        iva_row.addWidget(note('Separar IVA del total'))
        self.invoice_vat_rate=AmountEdit(str(DisplayPreferences().purchase_vat_rate()))
        self.invoice_vat_rate.setMaximumWidth(76)
        self.invoice_vat_rate.setStyleSheet('padding: 3px 8px;')
        self.invoice_vat_rate.setAccessibleName('Tarifa de IVA del total')
        iva_row.addWidget(self.invoice_vat_rate);iva_row.addWidget(note('%'));iva_row.addStretch()
        products.addLayout(iva_row)
        self.invoice_vat_summary=self.products_total
        self.invoice_vat_enabled.setToolTip('El total de mercancía ingresado ya incluye IVA. Se separa la base sin aumentar el total. No se combina con IVA por producto.')
        buttons=QHBoxLayout(); self.add_line=QPushButton('+ Agregar producto'); self.add_line.setObjectName('secondaryAction')
        self.edit_line=QPushButton('Editar'); self.remove_line=QPushButton('Quitar')
        for b in (self.add_line,self.edit_line,self.remove_line): buttons.addWidget(b)
        products.addLayout(buttons)
        self.costs_panel,costs=section('3 · Costos adicionales')
        self.update_concepts_button=QPushButton('Actualizar conceptos');self.update_concepts_button.setToolTip('Aplica las reglas actuales de subtipo y producto conservando los cargos y asignaciones existentes.');self.update_concepts_button.clicked.connect(self.update_concepts)
        self.update_concepts_button.setStyleSheet('font-size: 12px; padding: 2px 8px;')
        cost_heading=QHBoxLayout();cost_heading.addWidget(costs.takeAt(0).widget(),1);cost_heading.addWidget(self.update_concepts_button);costs.insertLayout(0,cost_heading)
        self.concepts_notice=note('');self.concepts_notice.hide();costs.addWidget(self.concepts_notice)
        self.progress_editor=PurchaseProgressEditor(inline=True,categories=self.categories)
        self.progress_editor.set_states({key:'unselected' for key in self.categories},False)
        costs.addWidget(self.progress_editor)
        self.cost_editor=PurchaseCostEditor(categories=self.categories); self.cost_editor.bind_progress(self.progress_editor)
        self.cost_editor.validate_candidate=self.validate_cost_candidate
        costs.addWidget(self.cost_editor,1)
        self.costs_state=self.progress_editor.legacy
        self.distribute_costs=QPushButton('Distribuir costos entre productos');self.distribute_costs.setObjectName('secondaryAction')
        self.distribute_costs.clicked.connect(self.open_allocations);costs.addWidget(self.distribute_costs)
        self.vat_note=note('');costs.addWidget(self.vat_note)
        self.allocation_note=note(''); costs.addWidget(self.allocation_note)
        self.status_hint=note(''); body.addWidget(self.status_hint)
        self.summary_grid=QGridLayout(); self.summary_frames=[]; self.summary_labels=[]
        for title,style in [('Mercancía','chargeSummary'),('Envío e importación','expenseSummary'),('Impuestos y otros','expenseSummary'),('Total registrado · COP','netSummary')]:
            frame=QFrame(); frame.setObjectName(style); box=QVBoxLayout(frame); box.setContentsMargins(10,7,10,7)
            box.addWidget(note(title,'fieldHeading')); amount=note('—','summaryAmount'); box.addWidget(amount)
            self.summary_frames.append(frame); self.summary_labels.append(amount)
        root.addLayout(self.summary_grid)
        self.error=note('','error'); root.addWidget(self.error)
        footer=QHBoxLayout(); self.cancel_purchase=QPushButton('Anular compra'); self.cancel_purchase.setObjectName('removeAction')
        self.history_button=QPushButton('Historial'); self.reload_button=QPushButton('Recargar')
        for b in (self.cancel_purchase,self.history_button,self.reload_button): b.setVisible(purchase_id is not None); footer.addWidget(b)
        self.reverse_receipt_button=QPushButton('Deshacer recepción');self.reverse_receipt_button.setObjectName('removeAction');self.reverse_receipt_button.hide()
        self.reverse_receipt_button.clicked.connect(self.reverse_receipt);footer.addWidget(self.reverse_receipt_button)
        if purchase_id is not None:footer.addWidget(attachment_button(purchases.connection,'purchase',purchase_id,self))
        footer.addStretch(); close=QPushButton('Cancelar' if purchase_id is None else 'Cerrar')
        self.save_button=QPushButton('Guardar compra'); self.save_button.setObjectName('primary'); self.save_button.setDefault(True)
        footer.addWidget(close); footer.addWidget(self.save_button); root.addLayout(footer)
        close.clicked.connect(self.reject); self.save_button.clicked.connect(self.save)
        self.add_line.clicked.connect(lambda:self.open_line_editor()); self.edit_line.clicked.connect(self.edit_selected)
        self.remove_line.clicked.connect(self.remove_selected); self.lines_table.cellDoubleClicked.connect(self.edit_selected)
        self.cost_editor.changed.connect(self.refresh_summary); self.progress_editor.changed.connect(self.refresh_summary)
        self.purchased_on.dateChanged.connect(self.refresh_summary); self.supplier.textChanged.connect(self.refresh_summary)
        self.cancel_purchase.clicked.connect(self.cancel_record); self.history_button.clicked.connect(self.show_history); self.reload_button.clicked.connect(self.reload)
        self.invoice_vat_enabled.toggled.connect(self.toggle_invoice_vat)
        self.invoice_vat_rate.textChanged.connect(self.refresh_summary)
        self._arrange(self.width()<1050)
        if purchase_id: self.load()
        else: self.refresh_summary()

    def _arrange(self,compact):
        if self._compact==compact: return
        self._compact=compact
        for grid in (self.grid,self.summary_grid):
            while grid.count(): grid.takeAt(0)
            for col in range(4): grid.setColumnStretch(col,0)
        self.grid.addWidget(self.products_panel,0,0); self.grid.addWidget(self.costs_panel,1 if compact else 0,0 if compact else 1)
        self.grid.setColumnStretch(0,1); self.grid.setColumnStretch(1,0 if compact else 1)
        for i,frame in enumerate(self.summary_frames): self.summary_grid.addWidget(frame,i//(2 if compact else 4),i%(2 if compact else 4))
        for col in range(2 if compact else 4): self.summary_grid.setColumnStretch(col,1)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.layout().setSpacing(4 if self.height()<800 else 6)
        if hasattr(self,'costs_panel'):
            padding=5 if self.height()<800 else 8
            for panel in (self.header,self.products_panel,self.costs_panel):
                panel.layout().setContentsMargins(12,padding,12,padding)
        if hasattr(self,'summary_grid'): self._arrange(self.width()<1050)

    def select_supplier(self,text):
        if text in self.supplier_suggestions:
            name,alias=self.supplier_suggestions[text]
            self.supplier.setText(name);self.supplier_alias.setText(alias)

    def covered_vat_categories(self):
        if not self.invoice_vat_enabled.isChecked() and not any(line.vat_enabled for line in self.lines):return set()
        used={cost.category for cost in self.cost_editor.costs()}
        return {key for key,name in self.categories.items() if is_vat_cost(name) and key not in used}

    def validate_cost_candidate(self,cost,index):
        costs=list(self.cost_editor.costs())
        if index is None:costs.append(cost)
        else:costs[index]=cost
        check_duplicate_vat(replace(self.draft(),costs=tuple(costs)))

    def toggle_invoice_vat(self,enabled):
        if enabled:
            try:check_duplicate_vat(self.draft())
            except ValidationError as exc:
                with QSignalBlocker(self.invoice_vat_enabled):self.invoice_vat_enabled.setChecked(False)
                self.error.setText(error_text(exc))
                self.refresh_summary()
                return
        self.error.clear()
        self.refresh_summary()

    def draft(self):
        states=self.progress_editor.states()
        if states is not None:
            states={**states,**{key:'not_applicable' for key in self.covered_vat_categories()}}
        complete=cost_states_complete(states) if states is not None else self.progress_editor.is_complete()
        return PurchaseDraft(self.purchased_on.date().toPython(),self.supplier.text().strip(),self.reference.text().strip(),
                             tuple(self.lines),self.cost_editor.costs(),complete,states,self.cost_definitions,self.supplier_alias.text().strip(),self.tracking.text().strip(),
                             self.invoice_vat_enabled.isChecked(),
                             (Decimal('NaN') if self.invoice_vat_enabled.isChecked() else Decimal('19')) if rate_issue(self.invoice_vat_rate,'IVA',100) else Decimal(self.invoice_vat_rate.text().replace(',','.')))

    def refresh_summary(self,*args):
        self.invoice_vat_rate.setEnabled(self.invoice_vat_enabled.isChecked())
        self.cost_editor.setEnabled(bool(self.lines))
        self.cost_editor.description.setVisible(not self.lines)
        self.cost_editor.description.setText('Agrega los productos para determinar los costos adicionales aplicables.')
        self.cost_editor.table.setVisible(bool(self.lines))
        automatic = bool(self.lines) and len({line.product_id for line in self.lines}) == 1
        if getattr(self, '_automatic_allocation_active', False) and not automatic:
            self.lines = [replace(line, **{field: 0 for field in ALLOCATION_FIELDS.values()},
                                  extra_allocations={}) for line in self.lines]
            self._render_lines()
        self._automatic_allocation_active = automatic
        self.distribute_costs.setEnabled(bool(self.lines) and not automatic)
        self.distribute_costs.setText(
            'Reparto automático · mismo modelo' if automatic else 'Distribuir costos entre productos')
        try:
            normalized = automatic_allocations(apply_invoice_vat(self.draft()))
            if tuple(self.lines) != normalized.lines:
                self.lines = list(normalized.lines)
                self._render_lines()
        except ValidationError:
            pass  # The summary below displays the invalid amount/rate.
        draft=self.draft()
        complete=draft.costs_complete
        states=draft.cost_states
        covered=self.covered_vat_categories()
        self.cost_editor.blocked_categories={key for key,name in self.categories.items() if is_vat_cost(name)} if self.invoice_vat_enabled.isChecked() or any(line.vat_enabled for line in self.lines) else set()
        for row,key in enumerate(self.cost_editor.row_categories):
            self.cost_editor.table.setRowHidden(row,key in covered)
        self.progress_editor.setVisible(states is None)
        pending=', '.join(self.categories[key] for key,value in (states or {}).items() if value=='pending')
        unselected=', '.join(self.categories[key] for key,value in (states or {}).items() if value=='unselected')
        details=[]
        if pending:details.append('Pendiente: '+pending)
        if unselected:details.append('Sin seleccionar: '+unselected)
        self.status_hint.setText('Costos completos · no registra pagos ni movimientos de inventario.' if complete else
                                'Provisional · '+(' · '.join(details) or 'revisar conceptos pendientes'))
        try:
            summary=allocation_summary(self.draft())
            self.allocation_note.setText('Gastos asignados: '+format_cop(sum(summary['assigned'].values()))+
                ' · Por asignar: '+format_cop(sum(summary['remaining'].values())))
            self.allocation_note.setToolTip('\n'.join(self.categories[key]+': registrado '+format_cop(summary['registered'][key])+
                ' · asignado '+format_cop(summary['assigned'][key])+' · pendiente '+format_cop(value)
                for key,value in summary['remaining'].items()))
            totals=preview_purchase_totals(self.draft())
            self.products_total.setText('Total de productos (base): '+format_cop(totals.merchandise_cents) if totals.vat_cents else 'Total de productos: '+format_cop(totals.merchandise_cents))
            if self.invoice_vat_enabled.isChecked():
                self.products_total.setText('Base: '+format_cop(totals.merchandise_cents)+' · IVA: '+format_cop(totals.vat_cents))
                self.products_total.setToolTip('Mercancía con IVA incluido: '+format_cop(totals.merchandise_cents+totals.vat_cents))
            else:self.products_total.setToolTip('Total de mercancía, sin gastos adicionales.')
            self.vat_note.setVisible(any(line.vat_enabled for line in self.lines))
            self.vat_note.setText('IVA de productos: '+format_cop(totals.vat_cents)+' · Incluido en Impuestos y otros. IVA de factura bloqueado mientras haya IVA por producto.')
            if complete and not summary['complete']:
                self.status_hint.setText('Provisional · faltan gastos por asignar a las máquinas.')
            for label,value in zip(self.summary_labels,(totals.merchandise_cents,totals.shipping_import_cents,totals.taxes_other_cents,totals.total_cents)):
                label.setText(format_cop(value))
        except ValidationError as error:
            self.invoice_vat_summary.setText('Revisa la tarifa o los importes del IVA.')
            self.vat_note.show();self.vat_note.setText(error_text(error))
            self.products_total.setText('Total de productos: revisa los importes')
            for label in self.summary_labels: label.setText('Revisa los importes' if self.lines else '—')

    def refresh_lines(self):
        if not self.purchase_id:self.sync_applicable_costs()
        self._render_lines()
        self.refresh_summary()

    def _render_lines(self):
        self.lines_table.setRowCount(len(self.lines))
        for i,line in enumerate(self.lines):
            name=self.names.get(line.line_id,self.product_names.get(line.product_id,'Producto no disponible'))
            units=line_unit_costs(line)
            prefix='≈ ' if units['approximate'] else ''
            from decimal import ROUND_HALF_UP
            values=[name,str(line.quantity),prefix+format_cop(int(units['purchase_cents'].quantize(Decimal('1'),rounding=ROUND_HALF_UP))),
                    prefix+format_cop(int(units['landed_cents'].quantize(Decimal('1'),rounding=ROUND_HALF_UP))),
                    format_cop(line_base_cop(line))]
            for j,text in enumerate(values):
                item=QTableWidgetItem(text); item.setToolTip(text); self.lines_table.setItem(i,j,item)

    def open_line_editor(self,index=None):
        if self.line_dialog and self.line_dialog.isVisible(): self.line_dialog.raise_(); return self.line_dialog
        try:
            products=self.catalog.list_products(kind='product',active=True)
            self.product_names.update({p.id:p.code+' · '+p.name for p in products})
            line=self.lines[index] if index is not None else None
            self.line_dialog=PurchaseLineDialog(products,line,self.names.get(line.line_id,'Producto histórico') if line else '',self)
            dialog=self.line_dialog
            def validate_line(candidate):
                lines=list(self.lines)
                if index is None:lines.append(candidate)
                else:lines[index]=candidate
                check_duplicate_vat(replace(self.draft(),lines=tuple(lines)))
            dialog.validate_candidate=validate_line
            if self.invoice_vat_enabled.isChecked():
                dialog.vat.enabled.setChecked(False)
                dialog.vat.enabled.setEnabled(False)
                dialog.vat.setToolTip('El IVA se está separando del total del pedido. Desactiva esa opción antes de usar IVA por producto.')
            if any(is_vat_cost(self.categories.get(cost.category,''),cost.description) and cost.amount_cents for cost in self.cost_editor.costs()):
                dialog.error.setText('Ya hay IVA de factura en Costos adicionales. Quítalo antes de aplicar IVA por producto.')
                if line is None or not line.vat_enabled:
                    dialog.vat.enabled.setChecked(False)
                    dialog.vat.enabled.setEnabled(False)
                    dialog.vat.setToolTip('Quita primero el cargo de IVA de la factura para usar IVA por producto.')
            if getattr(self,'record',{}).get('receipt'):dialog.quantity.setEnabled(False)
            def applied():
                if index is None: self.lines.append(dialog.result_line)
                else: self.lines[index]=dialog.result_line
                self.refresh_lines()
            dialog.accepted.connect(applied); dialog.show(); return dialog
        except StorageError as error: self.error.setText(str(error))

    def open_allocations(self):
        if not self.lines:
            self.error.setText('Agrega primero los productos de la compra.');return
        from .purchase_allocation_dialog import PurchaseAllocationDialog
        names=[self.names.get(line.line_id,self.product_names.get(line.product_id,'Producto')) for line in self.lines]
        self.allocation_dialog=PurchaseAllocationDialog(self.draft(),names,self)
        dialog=self.allocation_dialog
        def applied():
            self.lines=list(dialog.result_lines);self.refresh_lines()
        dialog.accepted.connect(applied);dialog.show()

    def edit_selected(self,*args):
        index=self.lines_table.currentRow()
        if 0<=index<len(self.lines): self.open_line_editor(index)

    def remove_selected(self):
        index=self.lines_table.currentRow()
        if 0<=index<len(self.lines): self.lines.pop(index); self.refresh_lines()

    def _set_concepts(self,definitions,states,complete):
        old=self.progress_editor
        old.changed.disconnect(self.refresh_summary)
        old.changed.disconnect(self.cost_editor.sync_states)
        self.cost_definitions=dict(definitions)
        self.categories={key:value['name'] for key,value in definitions.items()}
        self.progress_editor=PurchaseProgressEditor(inline=True,categories=self.categories)
        self.progress_editor.set_states(states,complete)
        self.costs_panel.layout().replaceWidget(old,self.progress_editor)
        old.hide();old.deleteLater()
        self.costs_state=self.progress_editor.legacy
        self.cost_editor.categories=dict(self.categories)
        self.cost_editor.bind_progress(self.progress_editor)
        self.progress_editor.changed.connect(self.refresh_summary)

    def sync_applicable_costs(self,explicit=False):
        available=PurchaseCostRules(self.catalog.connection).definitions(line.product_id for line in self.lines)
        # Keep every entered charge and assignment even if current rules exclude it.
        used={cost.category for cost in self.cost_editor.costs()}
        for line in self.lines:
            used.update(key for key,field in ALLOCATION_FIELDS.items() if getattr(line,field))
            used.update(key for key,value in line.extra_allocations.items() if value)
        kept=used-set(available)
        definitions={key:self.cost_definitions.get(key,value) for key,value in available.items()}
        definitions.update({key:self.cost_definitions[key] for key in self.cost_definitions if key in kept})
        old_states=self.progress_editor.states()
        if definitions!=self.cost_definitions:
            if old_states is None:
                complete=self.progress_editor.is_complete()
                old_states={key:('recorded' if key in used else 'not_applicable') if complete else ('recorded' if key in used else 'unselected') for key in self.categories}
            states={key:old_states.get(key,'unselected') for key in definitions}
            self._set_concepts(definitions,states,cost_states_complete(states))
        if kept:
            self.concepts_notice.setText('Se conservan costos con importes o asignaciones que ya no aplican: '+', '.join(self.categories.get(key,key) for key in sorted(kept))+'. Revisa antes de guardar.')
        elif explicit:
            self.concepts_notice.setText('Conceptos actualizados según los subtipos y excepciones de los productos. Se conservaron los importes existentes.')
        else:self.concepts_notice.clear()
        self.concepts_notice.setVisible(bool(self.concepts_notice.text()))

    def update_concepts(self):
        if self.purchase_id and self.record['cancelled_at']:return
        self.sync_applicable_costs(explicit=True)
        self.refresh_summary()

    def load(self):
        row=self.purchases.get(self.purchase_id); self.revision=row['revision']; self.record=row
        if self.cost_definitions!=row['cost_definitions']:
            self._set_concepts(row['cost_definitions'],row.get('cost_states'),bool(row['costs_complete']))
        with QSignalBlocker(self.invoice_vat_enabled), QSignalBlocker(self.invoice_vat_rate):
            self.invoice_vat_enabled.setChecked(bool(row.get('invoice_vat_enabled',False)))
            self.invoice_vat_rate.setText(row.get('invoice_vat_rate','19'))
        self.concepts_notice.hide()
        self.tracking.setText(row.get('tracking_number',''))
        self.supplier.setText(row['supplier']);self.supplier_alias.setText(row.get('supplier_alias','')); self.reference.setText(row['reference'])
        self.purchased_on.setDate(QDate.fromString(row['purchased_on'],'yyyy-MM-dd'))
        self.progress_editor.set_states(row.get('cost_states'),bool(row['costs_complete']))
        self.lines=[]; self.names={}
        for r in row['lines']:
            self.lines.append(PurchaseLineInput(r['product_id'],r['quantity'],r['unit_cost_cents'],r['currency'],
                Decimal(r['exchange_rate']) if r['exchange_rate'] is not None else None,
                date.fromisoformat(r['converted_on']) if r['converted_on'] else None,r['id'],
                invoice_vat_share_cents=r.get('vat_cents',0) if row.get('invoice_vat_enabled') else None,
                vat_enabled=bool(r.get('vat_enabled',False)),vat_rate=Decimal(r.get('vat_rate','19')),vat_included=bool(r.get('vat_included',False)),total_cost_cents=r.get('total_cost_cents'),extra_allocations=json.loads(r.get('extra_allocations_json') or '{}'), **{field:r.get(field,0) for field in ALLOCATION_FIELDS.values()}))
            self.names[r['id']]=r['code']+' · '+r['name']
        self._automatic_allocation_active = bool(self.lines) and len({line.product_id for line in self.lines}) == 1
        self.cost_editor.set_costs(tuple(PurchaseCostInput(r['category'],r['description'],r['amount_cents'],r['currency'],
            Decimal(r['exchange_rate']) if r['exchange_rate'] is not None else None,
            date.fromisoformat(r['converted_on']) if r['converted_on'] else None) for r in row['costs']))
        self.refresh_lines(); cancelled=bool(row['cancelled_at'])
        for widget in (self.header,self.products_panel,self.costs_panel,self.costs_state): widget.setEnabled(not cancelled)
        self.save_button.setVisible(not cancelled); self.cancel_purchase.setVisible(not cancelled)
        received=bool(row['receipt'])
        self.add_line.setEnabled(not received);self.remove_line.setEnabled(not received)
        self.reverse_receipt_button.setVisible(received and not cancelled)
        self.cancel_purchase.setEnabled(not received)
        if received:self.status_hint.setText(self.status_hint.text()+' · Recibido: '+row['receipt']['received_on'])
        if cancelled: self.status_hint.setText('Anulada · '+row['cancellation_reason'])

    def save(self):
        issues=[required(self.supplier,'el proveedor')]
        if self.invoice_vat_enabled.isChecked():issues.append(rate_issue(self.invoice_vat_rate,'IVA',100))
        if not self.lines:issues.append((self.add_line,'Agrega al menos un producto a la compra.'))
        if not check(self,issues,self.error):return
        self.save_button.setEnabled(False)
        try:
            draft=self.draft()
            row=(self.purchases.update(self.purchase_id,draft,expected_revision=self.revision) if self.purchase_id else
                 self.purchases.create(draft,request_id=self.request_id))
            self.saved.emit(row['id']); self.accept()
        except (ValidationError,StorageError) as error: self.error.setText(error_text(error))
        finally: self.save_button.setEnabled(True)

    def reload(self):
        if QMessageBox.question(self,'Recargar compra','Se descartarán los cambios sin guardar. ¿Recargar?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            try: self.load(); self.error.clear()
            except StorageError as error: self.error.setText(str(error))

    def reverse_receipt(self):
        reason,ok=required_reason(self,'Deshacer recepción','Motivo obligatorio · se retirarán estas entradas y se conservará el historial:')
        if not ok:return
        if QMessageBox.question(self,'Confirmar','¿Deshacer la recepción? Los cambios del formulario sin guardar se descartarán.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:
            PurchaseReceiptsRepository(self.purchases.connection).reverse(self.record['receipt']['id'],reason,expected_revision=self.revision)
            self.saved.emit(self.purchase_id);self.load()
        except StorageError as error:self.error.setText(str(error))

    def cancel_record(self):
        reason,ok=required_reason(self,'Anular compra','Motivo · se conservará el historial y se excluirá de los totales vigentes:')
        if not ok: return
        try:
            self.purchases.cancel(self.purchase_id,reason,expected_revision=self.revision)
            self.saved.emit(self.purchase_id); self.load()
        except StorageError as error: self.error.setText(str(error))

    def show_history(self):
        try:
            row=self.purchases.get(self.purchase_id)
            receipt_history=PurchaseReceiptsRepository(self.purchases.connection).history(self.purchase_id)
        except StorageError as error: self.error.setText(str(error)); return
        dialog=QDialog(self); dialog.setWindowTitle('Historial de compra'); dialog.resize(700,500)
        root=QVBoxLayout(dialog); text=QTextEdit(); text.setReadOnly(True)
        entries=[]
        from ..purchases import CATEGORIES
        for revision in row['revisions']:
            snapshot=revision['snapshot']
            lines=[f"Revisión {revision['revision']} · {revision['changed_at']}",
                   f"Proveedor: {snapshot['supplier']} · Alias: {snapshot.get('supplier_alias') or 'Sin alias'} · Fecha: {snapshot['purchased_on']}",
                   f"Referencia: {snapshot['reference'] or 'Sin referencia'}",
                   f"Guía / tracking: {snapshot.get('tracking_number') or 'Sin registrar'}",
                   'Costos completos' if snapshot['costs_complete'] else 'Costos por completar']
            historic={k:v['name'] for k,v in snapshot.get('cost_definitions',self.cost_definitions).items()}
            for item in snapshot['lines']:
                lines.append(f"{item['quantity']} × {item['code']} · {item['name']} — {format_cop(item['subtotal_cents'])} COP")
                if all(field in item for field in ALLOCATION_FIELDS.values()):
                    lines.append('  Gastos asignados: '+', '.join(historic.get(key,CATEGORIES[key])+': '+format_cop(item[field]) for key,field in ALLOCATION_FIELDS.items() if key in historic or item[field]))
                else: lines.append('  Asignación no registrada')
                for key,value in json.loads(item.get('extra_allocations_json') or '{}').items():
                    lines.append('  '+historic.get(key,key)+': '+format_cop(value))
            historic={k:v['name'] for k,v in snapshot.get('cost_definitions',self.cost_definitions).items()}
            states=snapshot.get('cost_states')
            labels={'unselected':'Sin seleccionar','pending':'Pendiente','recorded':'Registrado','not_applicable':'No aplica'}
            lines.append('Conceptos: '+(', '.join(historic.get(key,key)+': '+labels[value] for key,value in states.items()) if states else 'Seguimiento no registrado'))
            for item in snapshot['costs']:
                lines.append(f"{historic.get(item['category'],item['category'])}: {format_cop(item['subtotal_cents'])} COP · {item['description']}")
            lines.append('Total registrado: '+format_cop(snapshot['total_cents'])+' COP')
            entries.append('\n'.join(lines))
        for receipt in receipt_history:
            entries.append('Recepción #'+str(receipt['id'])+' · '+receipt['received_on']+' · '+str(sum(line['quantity'] for line in receipt['lines']))+' unidades'+
                ('\nDeshecha: '+receipt['reversed_at']+' · '+receipt['reversal_reason'] if receipt['reversed_at'] else ' · Vigente'))
        text.setPlainText('\n\n'.join(entries) or 'Aún no hay correcciones anteriores.')
        root.addWidget(text); close=QPushButton('Cerrar'); close.clicked.connect(dialog.accept); root.addWidget(close); dialog.show()
