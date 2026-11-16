"""Configuración acotada a formas de pago y cuentas."""
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QCheckBox,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QTabWidget,QScrollArea,QMessageBox)
from .form_validation import check, required, amount_issue, rate_issue
from ..sales import PaymentMethod, Account, money
from ..storage import StorageError
from ..catalog import ValidationError
from .sales_widgets import note, cents_text, error_text
from .carriers_editor import CarriersEditor
from .preferences import DisplayPreferences


class SettingsEditor(QWidget):
    changed=Signal()
    def __init__(self,repository,methods=True):
        super().__init__();self.setObjectName("settingsEditor");self.repository=repository;self.methods=methods;self.key=0;self.rows=[]
        root=QVBoxLayout(self)
        self.table=QTableWidget(0,3 if methods else 2)
        self.table.setHorizontalHeaderLabels(['Nombre','Comisión','Estado'] if methods else ['Cuenta','Estado'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMaximumHeight(240);self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(42);root.addWidget(self.table)
        form=QFormLayout();self.name=QLineEdit();self.enabled=QCheckBox('Habilitada');self.enabled.setChecked(True)
        form.addRow('Nombre',self.name)
        if methods:
            self.provider=QLineEdit();self.rate=QLineEdit('0');self.fixed=QLineEdit('0');self.placement=QComboBox();self.placement.addItem('Principal','primary');self.placement.addItem('Adicional','additional');self.received=QCheckBox('Proponer dinero recibido al elegirla')
            self.tiers=();self.tiers_button=QPushButton('Tarifas por monto · 0');self.tiers_button.clicked.connect(self.edit_tiers)
            form.addRow(self.tiers_button)
            form.addRow('Proveedor (opcional)',self.provider);form.addRow('Comisión %',self.rate);form.addRow('Cargo fijo · COP',self.fixed);form.addRow('En venta rápida',self.placement);form.addRow(self.received)
        self.account_kind=QComboBox()
        if methods:
            self.account_kind.addItem('Cualquier cuenta','any')
            self.account_kind.addItem('Proponer efectivo (permite cambiar)','cash')
            self.account_kind.addItem('Solo bancos y billeteras','bank')
            form.addRow('Cuentas al cobrar',self.account_kind)
        else:
            self.account_kind.addItem('Banco o billetera (Nequi, Daviplata…)','bank')
            self.account_kind.addItem('Caja de efectivo','cash')
            form.addRow('Tipo de cuenta',self.account_kind)
            self.default_account=QCheckBox('Predeterminada para este tipo de cuenta')
            form.addRow(self.default_account)
        form.addRow(self.enabled);root.addLayout(form)
        buttons=QHBoxLayout();new=QPushButton('Crear nueva');self.save=QPushButton('Guardar cambios');self.save.setObjectName('primary');buttons.addWidget(new);buttons.addWidget(self.save);root.addLayout(buttons)
        self.error=note('','error');root.addWidget(self.error);root.addStretch()
        new.clicked.connect(self.clear);self.save.clicked.connect(self.persist);self.table.itemSelectionChanged.connect(self.select)
        self.refresh()

    def refresh(self):
        try:
            self.rows=self.repository.list_methods(True) if self.methods else self.repository.list_accounts(True)
            self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                values=[row.name]
                if self.methods: values.append(f'{row.rate_percent} % + {cents_text(row.fixed_cents)} COP'+(f' · {len(row.tiers)} tramos' if row.tiers else ''))
                values.append('Habilitada' if row.enabled else 'Deshabilitada')
                for j,value in enumerate(values): self.table.setItem(i,j,QTableWidgetItem(value))
            self.error.clear()
        except StorageError as e: self.error.setText(str(e))

    def select(self):
        i=self.table.currentRow()
        if not 0<=i<len(self.rows):return
        row=self.rows[i];self.key=row.id;self.name.setText(row.name);self.enabled.setChecked(row.enabled)
        self.account_kind.setCurrentIndex(self.account_kind.findData(row.account_kind if self.methods else row.kind))
        if not self.methods:self.default_account.setChecked(row.is_default)
        if self.methods:
            self.tiers=row.tiers;self.tiers_button.setText(f'Tarifas por monto · {len(self.tiers)}')
            self.provider.setText(row.provider);self.rate.setText(str(row.rate_percent));self.fixed.setText(cents_text(row.fixed_cents));self.placement.setCurrentIndex(self.placement.findData(row.placement));self.received.setChecked(row.default_received)

    def clear(self):
        self.table.clearSelection();self.table.setCurrentCell(-1,-1);self.key=0;self.name.clear();self.enabled.setChecked(True)
        if self.methods:
            self.tiers=();self.tiers_button.setText('Tarifas por monto · 0')
            self.provider.clear();self.rate.setText('0');self.fixed.setText('0');self.placement.setCurrentIndex(1);self.received.setChecked(False)
        self.account_kind.setCurrentIndex(0)
        if not self.methods:self.default_account.setChecked(False)
        self.error.clear();self.name.setFocus()

    def edit_tiers(self):
        from .commission_tiers import CommissionTiersDialog
        dialog=CommissionTiersDialog(self.tiers,self)
        if dialog.exec():
            self.tiers=dialog.tiers;self.tiers_button.setText(f'Tarifas por monto · {len(self.tiers)}')

    def persist(self):
        issues=[required(self.name,'el nombre')]
        if self.methods:issues.extend([rate_issue(self.rate,'Comisión porcentual',100),amount_issue(self.fixed,'Comisión fija')])
        if not check(self,issues,self.error):return
        try:
            if self.methods:
                row=self.repository.save_method(PaymentMethod(self.key,self.name.text(),self.provider.text(),Decimal(self.rate.text().replace(',','.')),money(self.fixed.text()),self.enabled.isChecked(),self.placement.currentData(),self.received.isChecked(),self.account_kind.currentData(),self.tiers))
            else: row=self.repository.save_account(Account(self.key,self.name.text(),self.enabled.isChecked(),self.account_kind.currentData(),self.default_account.isChecked()))
            self.key=row.id;self.refresh()
            for i,r in enumerate(self.rows):
                if r.id==self.key:self.table.selectRow(i);break
            self.changed.emit()
        except (StorageError,ValidationError,InvalidOperation) as e:
            self.error.setText('Escribe un porcentaje válido.' if isinstance(e,InvalidOperation) else error_text(e))


class SettingsPage(QWidget):
    settings_changed=Signal()
    def __init__(self,repository,parent=None,preferences=None):
        super().__init__(parent);root=QVBoxLayout(self);root.setContentsMargins(24,18,24,18)
        root.addWidget(note('Configuración','heading'));root.addWidget(note('Personaliza tus formas de pago y cuentas. Los cambios no alteran ventas anteriores.'))
        self.preferences=preferences if preferences is not None else DisplayPreferences()
        tabs=QTabWidget();root.addWidget(tabs)
        root.addWidget(note('Nimbo · MIT © 2026 fandres323. Utiliza Qt / PySide6 bajo LGPLv3. Licencias, avisos y sustitución de bibliotecas: consulta los archivos incluidos con el programa.'))
        display=QWidget();display_box=QVBoxLayout(display)
        display_box.addWidget(note('Información de compras','cardTitle'))
        self.monthly_purchases=QCheckBox('Mostrar el total comprado en el mes actual')
        self.monthly_purchases.setChecked(self.preferences.show_monthly_purchases())
        display_box.addWidget(self.monthly_purchases)
        display_box.addWidget(note('Añade un resumen junto a la inversión total en Compras. Incluye mercancía y costos registrados de los pedidos vigentes del mes actual, sin aplicar los filtros del listado.'))
        display_box.addWidget(note('Desactivado de forma predeterminada. Esta preferencia se guarda en este equipo.'))
        self.display_error=note('','error');display_box.addWidget(self.display_error);display_box.addStretch()
        tabs.addTab(display,'Visualización')
        from .backup_page import BackupPage
        from ..backup_preferences import BackupPreferences
        self.backup_page=BackupPage(repository.connection,self,BackupPreferences(self.preferences.settings))
        tabs.addTab(self.backup_page,'Copias de seguridad')
        iva_page=QWidget();iva_box=QVBoxLayout(iva_page)
        iva_box.addWidget(note('IVA predeterminado','cardTitle'))
        iva_box.addWidget(note('Se aplica a nuevas ventas y a productos nuevos en compras. No cambia registros anteriores. Tarifa inicial: 19 %, editable en cada operación.'))
        self.vat_sales=QCheckBox('Activar IVA al crear una venta');self.vat_purchases=QCheckBox('Activar IVA al agregar un producto comprado')
        self.vat_error=note('','error')
        for control,area in ((self.vat_sales,'sales'),(self.vat_purchases,'purchases')):
            control.setChecked(self.preferences.vat_default(area));iva_box.addWidget(control)
            control.toggled.connect(lambda checked,a=area:self._save_vat_preference(a,checked))
        iva_box.addWidget(self.vat_error);iva_box.addStretch();tabs.addTab(iva_page,'IVA')

        from .purchase_concepts_editor import PurchaseConceptsEditor
        self.purchase_concepts=PurchaseConceptsEditor(repository.connection)
        tabs.addTab(self.purchase_concepts,'Costos de compras')
        self.purchase_concepts.changed.connect(self.settings_changed.emit)
        self.monthly_purchases.toggled.connect(self._save_display_preference)
        sale_options=QWidget();sale_box=QVBoxLayout(sale_options)
        sale_box.addWidget(note('Datos del cliente','cardTitle'))
        self.require_identification=QCheckBox('Exigir cédula o NIT en las nuevas ventas')
        self.require_identification.setChecked(self.preferences.require_sale_identification());sale_box.addWidget(self.require_identification)
        sale_box.addWidget(note('Desactivado por defecto. Si lo activas, será necesario completar el documento del cliente antes de guardar una nueva venta. El correo es opcional salvo que actives los requisitos de retención. No modifica ventas anteriores.'))
        self.require_retention=QCheckBox('Exigir factura y correo del cliente cuando se aplique retención')
        self.require_retention.setChecked(self.preferences.require_retention_documents());sale_box.addWidget(self.require_retention)
        sale_box.addWidget(note('Activado por defecto. Puedes desactivarlo para permitir guardar ventas con retención sin esos datos.'))
        self.require_retention.toggled.connect(self._save_retention_preference)
        from ..sales_repository import SalesRepository
        self.sales_management=SalesRepository(repository.connection)
        self.sale_permissions={}
        sale_box.addWidget(note('Gestión de ventas guardadas','cardTitle'))
        for action,title in [('cancel','Permitir anular ventas y conservar su historial'),('edit','Permitir editar ventas, productos, cantidades y precios'),('delete','Permitir eliminar ventas definitivamente')]:
            control=QCheckBox(title);control.setChecked(self.sales_management.permissions()[action])
            self.sale_permissions[action]=control;sale_box.addWidget(control)
            control.toggled.connect(lambda enabled,a=action:self._save_sale_permission(a,enabled))
        sale_box.addWidget(note('Eliminar está desactivado por defecto. Anular conserva la venta; eliminar borra la venta y sus cobros y pagos asociados. Cada eliminación requiere confirmación.'))
        self.sale_options_error=note('','error');sale_box.addWidget(self.sale_options_error);sale_box.addStretch();tabs.addTab(sale_options,'Ventas')
        self.require_identification.toggled.connect(self._save_sale_preference)
        from ..inventory_repository import InventoryRepository
        from .inventory_page import InventorySettings
        self.inventory_settings=InventorySettings(InventoryRepository(repository.connection))
        tabs.addTab(self.inventory_settings,'Inventario');self.inventory_settings.changed.connect(self.settings_changed.emit)
        from ..expenses_repository import ExpensesRepository
        from .expense_categories import ExpenseCategoriesEditor
        self.expense_categories=ExpenseCategoriesEditor(ExpensesRepository(repository.connection))
        tabs.addTab(self.expense_categories,'Gastos');self.expense_categories.changed.connect(self.settings_changed.emit)
        from ..credit_cards import CreditCardsRepository
        from .credit_card_dialogs import CardSettingsWidget
        self.card_settings=CardSettingsWidget(CreditCardsRepository(repository.connection))
        tabs.addTab(self.card_settings,'Dinero / tarjetas');self.card_settings.changed.connect(self.settings_changed.emit)
        self.method_editor=SettingsEditor(repository);self.account_editor=SettingsEditor(repository,False)
        from .unsaved_settings import UnsavedSettingsTracker
        self.unsaved_trackers=[UnsavedSettingsTracker(editor) for editor in (self.purchase_concepts.rules_editor,self.purchase_concepts,self.expense_categories,self.card_settings)]
        for title,editor in [('Formas de pago',self.method_editor),('Cuentas',self.account_editor),('Transportadoras',CarriersEditor(repository))]:
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(editor);tabs.addTab(scroll,title);editor.changed.connect(self.settings_changed.emit)
            self.unsaved_trackers.append(UnsavedSettingsTracker(editor))
        self.backup_page.has_unsaved_changes=lambda:any(tracker.dirty() for tracker in self.unsaved_trackers)
        self.purchase_concepts.rules_editor.changed.connect(self.settings_changed)

    def _save_display_preference(self,enabled):
        try:
            self.preferences.set_show_monthly_purchases(enabled)
            self.display_error.clear();self.settings_changed.emit()
        except OSError as error:
            self.display_error.setText(str(error))

    def _save_vat_preference(self,area,enabled):
        try:self.preferences.set_vat_default(area,enabled);self.vat_error.clear();self.settings_changed.emit()
        except OSError as error:self.vat_error.setText(str(error))

    def _save_sale_preference(self,enabled):
        try:
            self.preferences.set_require_sale_identification(enabled)
            self.sale_options_error.clear();self.settings_changed.emit()
        except OSError as error:self.sale_options_error.setText(str(error))

    def _save_retention_preference(self,enabled):
        try:
            self.preferences.set_require_retention_documents(enabled)
            self.sale_options_error.clear();self.settings_changed.emit()
        except OSError as error:self.sale_options_error.setText(str(error))


    def _save_sale_permission(self,action,enabled):
        control=self.sale_permissions[action]
        previous=self.sales_management.permissions()[action]
        if action=='delete' and enabled:
            answer=QMessageBox.warning(self,'Habilitar eliminación definitiva',
                'Podrás borrar ventas, sus cobros y pagos asociados. No podrán recuperarse desde el historial. Las copias de documentos se conservan en la carpeta de archivos.\n¿Quieres habilitar esta opción?',
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer!=QMessageBox.Yes:
                control.blockSignals(True);control.setChecked(previous);control.blockSignals(False);return
        try:
            self.sales_management.set_permission(action,enabled)
            self.sale_options_error.clear();self.settings_changed.emit()
        except StorageError as error:
            control.blockSignals(True);control.setChecked(previous);control.blockSignals(False)
            self.sale_options_error.setText(str(error))
