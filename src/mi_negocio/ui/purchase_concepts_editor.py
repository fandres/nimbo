"""Configuración de conceptos del punto 3 de las compras."""
from .purchase_cost_rules_editor import PurchaseCostRulesEditor
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QCheckBox,QPushButton,QTableWidgetItem,QTabWidget
from ..purchase_concepts import PurchaseConceptsRepository,GROUPS
from ..storage import StorageError
from .purchase_cost_editor import table
from .sales_widgets import note
from .form_validation import check,required


class PurchaseConceptsEditor(QWidget):
    changed=Signal()
    def __init__(self,connection,parent=None):
        super().__init__(parent);self.repository=PurchaseConceptsRepository(connection);self.key=None;self.rows=[]
        outer=QVBoxLayout(self); tabs=QTabWidget(); outer.addWidget(tabs)
        concepts=QWidget();root=QVBoxLayout(concepts);tabs.addTab(concepts,'Conceptos')
        self.rules_editor=PurchaseCostRulesEditor(connection);tabs.addTab(self.rules_editor,'Aplicación por producto')
        tabs.currentChanged.connect(lambda index:self.rules_editor.refresh() if index==1 else None)
        root.addWidget(note('Costos adicionales de compras','cardTitle'))
        root.addWidget(note('Configura los conceptos del punto 3. Las compras nuevas usan esta lista. En un pedido existente, usa Actualizar conceptos para incorporar conceptos nuevos sin cambiar los anteriores.'))
        self.table=table(['Concepto','Grupo del resumen','Estado']);root.addWidget(self.table,1)
        form=QFormLayout();self.name=QLineEdit();self.name.setMaxLength(100);self.group=QComboBox()
        for key,label in GROUPS.items():self.group.addItem(label,key)
        self.enabled=QCheckBox('Disponible en compras nuevas');self.enabled.setChecked(True)
        form.addRow('Nombre *',self.name);form.addRow('Grupo',self.group);form.addRow(self.enabled);root.addLayout(form)
        buttons=QHBoxLayout();self.new=QPushButton('+ Nuevo concepto');self.save=QPushButton('Guardar concepto');self.save.setObjectName('primary')
        self.remove=QPushButton('Quitar concepto');self.remove.setObjectName('removeAction')
        for button in (self.new,self.remove,self.save):buttons.addWidget(button)
        root.addLayout(buttons)
        root.addWidget(note('Quitar desactiva los conceptos usados o predefinidos; los personalizados sin uso se eliminan. Puedes volver a habilitar un concepto desactivado.'))
        self.error=note('','error');root.addWidget(self.error);self.status=note('');root.addWidget(self.status)
        self.new.clicked.connect(self.clear);self.save.clicked.connect(self.persist);self.remove.clicked.connect(self.remove_selected);self.table.itemSelectionChanged.connect(self.select);self.refresh()
    def refresh(self):
        self.rows=self.repository.list();self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            for j,value in enumerate((row['name'],GROUPS[row['summary_group']],'Activo' if row['enabled'] else 'Desactivado')):
                self.table.setItem(i,j,QTableWidgetItem(value))
        self.remove.setEnabled(self.key is not None)
    def clear(self):
        self.key=None;self.table.clearSelection();self.table.setCurrentCell(-1,-1);self.name.clear();self.enabled.setChecked(True);self.error.clear();self.status.clear();self.remove.setEnabled(False);self.name.setFocus()
    def select(self):
        i=self.table.currentRow()
        if not 0<=i<len(self.rows):return
        row=self.rows[i];self.key=row['key'];self.name.setText(row['name']);self.enabled.setChecked(bool(row['enabled']));self.group.setCurrentIndex(self.group.findData(row['summary_group']));self.remove.setEnabled(True)
    def persist(self):
        if not check(self,[required(self.name,'el nombre del concepto')],self.error):return
        try:
            row=self.repository.save(self.name.text(),self.group.currentData(),key=self.key,enabled=self.enabled.isChecked())
            self.key=row['key'];self.refresh()
            self.table.selectRow(next(i for i,r in enumerate(self.rows) if r['key']==self.key));self.status.setText('Concepto guardado. Para un pedido existente, abre la compra y pulsa Actualizar conceptos.');self.changed.emit()
        except StorageError as error:check(self,[(self.name,str(error))],self.error)
    def remove_selected(self):
        if not self.key:return
        try:
            result=self.repository.remove(self.key);self.clear();self.refresh();self.status.setText('Concepto desactivado; se conserva el historial.' if result=='disabled' else 'Concepto eliminado.');self.changed.emit()
        except StorageError as error:self.error.setText(str(error))
