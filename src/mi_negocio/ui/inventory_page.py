from .numeric_spinbox import NumericSpinBox as QSpinBox
"""Inventario visible, puesta en marcha y ajustes explícitos con historial."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,
    QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox,
    QRadioButton,QMessageBox,QDialogButtonBox,QFormLayout)
from .form_validation import check, required
from ..storage import StorageError
from .sales_widgets import note
from .style import STYLE


def table(headers):
    result=QTableWidget(0,len(headers));result.setHorizontalHeaderLabels(headers)
    result.verticalHeader().hide();result.verticalHeader().setDefaultSectionSize(48)
    result.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    result.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
    result.setEditTriggers(QTableWidget.NoEditTriggers);result.setSelectionBehavior(QTableWidget.SelectRows)
    result.setSelectionMode(QTableWidget.SingleSelection)
    return result


class InventorySetup(QDialog):
    def __init__(self, repository, parent=None):
        super().__init__(parent);self.repository=repository;self.preview=repository.preview()
        self.setWindowTitle('Iniciar inventario');self.resize(980,660);self.setStyleSheet(STYLE)
        root=QVBoxLayout(self);root.setContentsMargins(24,20,24,20);root.setSpacing(12)
        root.addWidget(note('Confirma tu inventario inicial','heading'))
        root.addWidget(note('Este paso se realiza una sola vez por base de datos. Las ventas anteriores no se descontarán.'))
        self.physical=QRadioButton('Confirmar existencias actuales por modelo · recomendado');self.physical.setChecked(True)
        self.physical.setStyleSheet('QRadioButton {background:#eaf0ff;color:#244fb8;padding:14px;border-radius:10px;font-weight:600;}')
        self.receipts=QRadioButton('Usar las compras recibidas registradas');root.addWidget(self.physical);root.addWidget(self.receipts)
        root.addWidget(note('Revisa también los modelos inactivos. En tránsito no significa disponible. Un cero confirma que no tienes unidades.'))
        self.table=table(['Código','Modelo','Compras recibidas','Existencias iniciales']);root.addWidget(self.table,1)
        self.table.setRowCount(len(self.preview['rows']));self.counts={}
        for index,row in enumerate(self.preview['rows']):
            for col,value in enumerate([row['code'],row['name']+(' · inactivo' if not row['active'] else ''),str(row['received'])]):self.table.setItem(index,col,QTableWidgetItem(value))
            count=QSpinBox();count.setRange(0,999999999);count.setAccessibleName('Existencias iniciales de '+row['name'])
            self.table.setCellWidget(index,3,count);self.counts[row['id']]=count
        self.physical_counts={key:0 for key in self.counts}
        self.receipts.toggled.connect(self.change_mode)
        self.reviewed=QCheckBox('Revisé todas las cantidades, incluidos los ceros. Confirmar iniciará el control de stock.');root.addWidget(self.reviewed)
        self.error=note('','error');root.addWidget(self.error)
        buttons=QHBoxLayout();later=QPushButton('Configurar después');later.clicked.connect(self.reject)
        self.confirm=QPushButton('Confirmar e iniciar inventario');self.confirm.setObjectName('primary');self.confirm.setEnabled(False)
        self.reviewed.toggled.connect(self.confirm.setEnabled);self.confirm.clicked.connect(self.persist)
        buttons.addWidget(later);buttons.addStretch();buttons.addWidget(self.confirm);root.addLayout(buttons)

    def change_mode(self, received):
        for row in self.preview['rows']:
            widget=self.counts[row['id']]
            if received:self.physical_counts[row['id']]=widget.value()
            widget.setValue(row['received'] if received else self.physical_counts[row['id']]);widget.setEnabled(not received)
        self.reviewed.setChecked(False)

    def persist(self):
        if not self.reviewed.isChecked():return
        try:
            self.repository.initialize('physical' if self.physical.isChecked() else 'receipts',
                {key:widget.value() for key,widget in self.counts.items()},expected_token=self.preview['token'])
            self.accept()
        except StorageError as error:self.error.setText(str(error))


class InventoryAdjustment(QDialog):
    def __init__(self, repository, row, parent=None):
        super().__init__(parent);self.repository=repository;self.row=row;self.revision=row['revision']
        self.setWindowTitle('Ajustar existencias');self.resize(600,350);self.setStyleSheet(STYLE)
        root=QVBoxLayout(self);root.addWidget(note(row['code']+' · '+row['name'],'cardTitle'))
        root.addWidget(note(f"Existencias actuales: {row['available']}. Este ajuste modifica el stock, no compras, ventas ni dinero."))
        form=QFormLayout();self.quantity=QSpinBox();self.quantity.setRange(0,999999999);self.quantity.setValue(row['available'])
        self.reason=QLineEdit();self.reason.setPlaceholderText('Explica por qué corriges las existencias')
        form.addRow('Nuevo stock',self.quantity);form.addRow('Motivo obligatorio',self.reason);root.addLayout(form)
        self.error=note('','error');root.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel);buttons.rejected.connect(self.reject)
        save=buttons.addButton('Revisar y guardar ajuste',QDialogButtonBox.AcceptRole);save.setObjectName('primary');save.clicked.connect(self.persist);root.addWidget(buttons)

    def persist(self):
        if not check(self,[required(self.reason,'el motivo del ajuste')],self.error):return
        quantity=self.quantity.value();old=self.row['available']
        response=QMessageBox.question(self,'Confirmar modificación del inventario',
            f"¿Estás seguro de modificar el stock de {self.row['code']} · {self.row['name']}?\n\nActual: {old}\nNuevo: {quantity}\nDiferencia: {quantity-old:+d}\nMotivo: {self.reason.text().strip()}",
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if response!=QMessageBox.Yes:return
        try:self.repository.adjust(self.row['id'],quantity,self.reason.text(),expected_revision=self.revision);self.accept()
        except StorageError as error:self.error.setText(str(error))


class InventorySettings(QWidget):
    changed=Signal()
    def __init__(self, repository, parent=None):
        super().__init__(parent);self.repository=repository;root=QVBoxLayout(self)
        root.addWidget(note('Ajustes manuales de inventario','cardTitle'))
        self.enabled=QCheckBox('Permitir modificar las existencias desde Inventario');root.addWidget(self.enabled)
        root.addWidget(note('Deshabilitado por defecto. Cada ajuste requiere motivo y confirmación; conserva el saldo anterior y el cambio en el historial de la máquina. Esta opción pertenece a esta base de datos.'))
        self.error=note('','error');root.addWidget(self.error);root.addStretch()
        self.refresh();self.enabled.toggled.connect(self.persist)

    def refresh(self):
        try:
            self.enabled.blockSignals(True);self.enabled.setChecked(bool(self.repository.state()['adjustments_enabled']))
        except StorageError as error:self.error.setText(str(error))
        finally:self.enabled.blockSignals(False)

    def persist(self, enabled):
        try:self.repository.set_adjustments_enabled(enabled);self.error.clear();self.changed.emit()
        except StorageError as error:self.error.setText(str(error));self.refresh()


class InventoryPage(QWidget):
    changed=Signal()
    def __init__(self, repository, parent=None):
        super().__init__(parent);self.repository=repository;self.rows=[]
        root=QVBoxLayout(self);root.setContentsMargins(24,18,24,18);root.setSpacing(14)
        heading=QHBoxLayout();heading.addWidget(note('Inventario','heading'));heading.addStretch()
        self.setup=QPushButton('Configurar inventario');self.setup.setObjectName('primary');self.setup.clicked.connect(self.open_setup);heading.addWidget(self.setup);root.addLayout(heading)
        self.summary=note('','cardTitle');root.addWidget(self.summary)
        self.explanation=note('');root.addWidget(self.explanation)
        filters=QHBoxLayout();self.search=QLineEdit();self.search.setClearButtonEnabled(True);self.search.setPlaceholderText('Buscar por código o modelo');filters.addWidget(self.search,1)
        refresh=QPushButton('Actualizar');refresh.clicked.connect(self.refresh);filters.addWidget(refresh);root.addLayout(filters)
        self.table=table(['Código','Modelo','Disponible','En tránsito','Recibidas¹','Vendidas²']);root.addWidget(self.table,1)
        root.addWidget(note('¹ Recepciones vigentes registradas. ² Ventas netas desde el inicio del control. El disponible incluye el saldo inicial y los ajustes.'))
        actions=QHBoxLayout();self.history_button=QPushButton('Ver historial');self.history_button.clicked.connect(self.open_history)
        self.adjust_button=QPushButton('Ajustar existencias');self.adjust_button.clicked.connect(self.open_adjust)
        actions.addWidget(self.history_button);actions.addWidget(self.adjust_button);actions.addStretch();root.addLayout(actions)
        self.error=note('','error');root.addWidget(self.error)
        self.search.textChanged.connect(self.refresh);self.table.itemSelectionChanged.connect(self.selection_changed);self.refresh()

    def refresh(self):
        try:
            self.state=self.repository.state();rows=self.repository.rows();query=self.search.text().strip().casefold()
            self.rows=[r for r in rows if query in (r['code']+' '+r['name']).casefold()]
            ready=self.state['initialized'];self.setup.setVisible(not ready)
            self.summary.setText((f"Disponibles: {sum(r['available'] for r in rows)}" if ready else 'Inventario sin configurar')+f"   ·   En tránsito: {sum(r['in_transit'] for r in rows)}")
            self.explanation.setText('Las nuevas ventas descuentan stock; anularlas devuelve las unidades.' if ready else 'Confirma las existencias iniciales. Hasta entonces, las ventas no controlan ni descuentan stock.')
            self.table.setRowCount(0);self.table.setRowCount(len(self.rows))
            for index,row in enumerate(self.rows):
                values=[row['code'],row['name']+(' · inactivo' if not row['active'] else ''),str(row['available']) if ready else 'Sin confirmar',row['in_transit'],row['received'],row['sold']]
                for col,value in enumerate(values):self.table.setItem(index,col,QTableWidgetItem(str(value)))
                if ready:
                    self.table.item(index,2).setForeground(QColor('#b42332' if row['available']==0 else '#996000' if row['available']<=2 else '#087544'))
            self.error.clear();self.selection_changed()
        except StorageError as error:self.error.setText(str(error))

    def selected(self):
        index=self.table.currentRow()
        return self.rows[index] if 0<=index<len(self.rows) else None

    def selection_changed(self):
        selected=self.selected() is not None
        self.history_button.setEnabled(selected)
        self.adjust_button.setEnabled(bool(selected and self.state['initialized'] and self.state['adjustments_enabled']))
        self.adjust_button.setToolTip('Habilita los ajustes manuales en Configuración → Inventario.')

    def completed(self):self.refresh();self.changed.emit()

    def open_setup(self):
        try:
            if self.repository.state()['initialized']:return
            if getattr(self,'setup_dialog',None) is not None and self.setup_dialog.isVisible():return
            self.setup_dialog=InventorySetup(self.repository,self);self.setup_dialog.accepted.connect(self.completed);self.setup_dialog.open()
        except StorageError as error:self.error.setText(str(error))

    def open_adjust(self):
        row=self.selected()
        if row is None:return
        try:
            state=self.repository.state()
            if not state['initialized'] or not state['adjustments_enabled']:raise StorageError('Habilita los ajustes en Configuración → Inventario.')
            current=self.repository.adjustment_preview(row['id'])
            self.adjust_dialog=InventoryAdjustment(self.repository,current,self)
            self.adjust_dialog.accepted.connect(self.completed);self.adjust_dialog.open()
        except StorageError as error:self.error.setText(str(error))

    def open_history(self):
        row=self.selected()
        if row is None:return
        try:history=self.repository.history(row['id'])
        except StorageError as error:self.error.setText(str(error));return
        dialog=QDialog(self);dialog.setWindowTitle('Historial · '+row['name']);dialog.resize(950,520);dialog.setStyleSheet(STYLE)
        root=QVBoxLayout(dialog);root.addWidget(note(row['code']+' · '+row['name'],'cardTitle'))
        grid=table(['Registrado','Motivo','Cambio','Saldo']);root.addWidget(grid);grid.setRowCount(len(history));balance=0
        for index,entry in enumerate(history):
            balance+=entry['delta']
            for col,value in enumerate([entry['created_at'],entry['reason'],f"{entry['delta']:+d}",balance]):grid.setItem(index,col,QTableWidgetItem(str(value)))
        close=QPushButton('Cerrar');close.clicked.connect(dialog.accept);root.addWidget(close);self.history_dialog=dialog;dialog.open()
