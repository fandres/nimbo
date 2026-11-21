"""Spreadsheet-like entry, with durable incomplete rows."""
import csv
import io
from datetime import date
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QTableWidget,
    QTableWidgetItem,QHeaderView,QApplication,QMessageBox,QStyledItemDelegate,QComboBox,QCompleter,QWidget)
from ..quick_entries import QuickEntriesRepository
from ..settings_repository import SettingsRepository
from ..expenses_repository import ExpensesRepository
from ..storage import StorageError
from .preferences import DisplayPreferences
from .sales_widgets import note
from .icons import icon

SALES=[('date','Fecha'),('customer','Cliente'),('product','Producto / código'),('quantity','Cant.'),('amount','Precio/u · COP'),('method','Forma de pago'),('account','Cuenta destino'),('paid','Cobrado'),('paid_on','Fecha de cobro'),('invoice','Factura'),('vat','IVA'),('rate','IVA %'),('withholding','Retención'),('email','Correo'),('identification','Cédula / NIT'),('alias','Alias / detalles'),('phone','Celular')]
EXPENSES=[('date','Fecha'),('concept','Concepto'),('category','Categoría'),('amount','Importe · COP'),('paid','Pagado'),('paid_on','Fecha de pago'),('account','Cuenta de pago'),('invoice','Comprobante'),('note','Nota')]


def quick_button(parent=None):
    button=QPushButton('Ingreso rápido',parent);button.setIcon(icon('table'));button.setCursor(Qt.PointingHandCursor)
    button.setToolTip('Registrar varias filas o completar pendientes')
    button.setStyleSheet('QPushButton {background:#e8eeff;color:#284bb5;border:1px solid #c6d3fa;border-radius:8px;padding:9px 14px;} QPushButton:hover {background:#d9e3ff;border-color:#315bea;} QPushButton:pressed {background:#ccd9ff;}')
    return button


class OptionsDelegate(QStyledItemDelegate):
    def __init__(self,options,parent):super().__init__(parent);self.options=options
    def createEditor(self,parent,option,index):
        editor=QComboBox(parent);editor.setEditable(True);editor.addItem('');editor.addItems(self.options)
        editor.setInsertPolicy(QComboBox.NoInsert)
        editor.completer().setCaseSensitivity(Qt.CaseInsensitive);editor.completer().setFilterMode(Qt.MatchContains)
        editor.completer().setCompletionMode(QCompleter.PopupCompletion)
        return editor
    def setEditorData(self,editor,index):editor.setEditText(index.data() or '')
    def setModelData(self,editor,model,index):model.setData(index,editor.currentText())


class EntryTable(QTableWidget):
    paste_requested=Signal()
    def keyPressEvent(self,event):
        if event.matches(QKeySequence.Paste):self.paste_requested.emit();return
        super().keyPressEvent(event)


class QuickEntryDialog(QDialog):
    saved=Signal()
    def __init__(self,connection,kind,parent=None,preferences=None,entry_id=None):
        super().__init__(parent)
        self.kind=kind;self.preferences=preferences or DisplayPreferences()
        self.repository=QuickEntriesRepository(connection,self.preferences)
        self.fields=SALES if kind=='sales' else EXPENSES
        self.records=[];self.original=[];self.dirty=False
        self.setWindowTitle('Ingreso rápido de '+('ventas' if kind=='sales' else 'gastos')+' — Nimbo');self.resize(1150,650)
        root=QVBoxLayout(self);root.addWidget(note('Ingreso rápido · '+('Ventas' if kind=='sales' else 'Gastos'),'heading'))
        root.addWidget(note('Cada fila es una operación independiente. Puedes guardar datos incompletos: quedarán en rojo como pendientes de completar.'))
        root.addWidget(note('Tab: siguiente celda · Ctrl+V: pegar filas sin encabezados · Fechas: dd/mm/aaaa · Importes en COP. Desliza horizontalmente para ver más campos.'))
        bar=QHBoxLayout()
        for title,callback in [('Agregar fila',self.add_row),('Duplicar fila',self.duplicate),('Quitar filas',self.remove_rows),('Pegar desde Excel',self.paste),('Reintentar pendientes',lambda:self.persist(retry=True))]:
            button=QPushButton(title);button.clicked.connect(callback);bar.addWidget(button)
        bar.addStretch();root.addLayout(bar)
        self.table=EntryTable(0,len(self.fields)+1);self.table.setHorizontalHeaderLabels([title for _,title in self.fields]+['Estado / por completar'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive);self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection);self.table.setTabKeyNavigation(True)
        widths={'date':110,'customer':175,'product':190,'quantity':65,'amount':145,'method':145,'account':155,'paid':85,'rate':75,'concept':220,'email':210}
        for i,(key,_) in enumerate(self.fields):self.table.setColumnWidth(i,widths.get(key,145))
        self.table.setColumnWidth(len(self.fields),420);root.addWidget(self.table,1)
        self.table.itemChanged.connect(self._edited);self.table.paste_requested.connect(self.paste)
        self.row_details=note('');root.addWidget(self.row_details)
        self.table.currentCellChanged.connect(self.show_row_details)
        self.status=note('');root.addWidget(self.status)
        root.addWidget(note('Las filas completas se registran. Las incompletas no mueven dinero ni existencias. Configuración → Ingreso rápido permite mostrarlas por separado como provisionales en informes.'))
        footer=QHBoxLayout();close=QPushButton('Cerrar');close.clicked.connect(self.reject);footer.addWidget(close)
        self.save_button=QPushButton('Guardar filas');self.save_button.setObjectName('primary');self.save_button.clicked.connect(self.persist);footer.addWidget(self.save_button);root.addLayout(footer)
        settings=SettingsRepository(connection)
        options={'paid':['No','Sí'],'withholding':['No','Sí'],'vat':['No aplica','Sumar IVA','IVA incluido'],
                 'method':[m.name for m in settings.list_methods()],
                 'account':[a.name for a in settings.list_accounts(include_cards=kind=='expenses')],
                 'category':[c['name'] for c in ExpensesRepository(connection).categories()],
                 'product':[r['code']+' · '+r['name'] for r in connection.execute('SELECT code,name FROM products WHERE active=1 ORDER BY code')]}
        for i,(key,_) in enumerate(self.fields):
            if key in options:self.table.setItemDelegateForColumn(i,OptionsDelegate(options[key],self.table))
        for record in self.repository.pending(kind):self.add_row(record=record)
        if entry_id:
            for i,record in enumerate(self.records):
                if record and record['id']==entry_id:self.table.setCurrentCell(i,0);self.table.scrollToItem(self.table.item(i,0));break
        self.add_row();self.dirty=False
        for button in self.findChildren(QPushButton):button.setAutoDefault(False)

    def show_row_details(self,row,*_):
        record=self.records[row] if 0<=row<len(self.records) else None
        text=record['error'] if record and record['operation_id'] is None else ''
        self.row_details.setText(('Fila '+str(row+1)+' · '+text) if text else '')

    def defaults(self):
        values={'date':date.today().strftime('%d/%m/%Y'),'paid':'No'}
        if self.kind=='sales':values.update(quantity='1',vat='Sumar IVA' if self.preferences.vat_default('sales') else 'No aplica',rate='19',withholding='No')
        return values

    def add_row(self,checked=False,record=None,payload=None):
        values=record['payload'] if record else (payload if payload is not None else self.defaults())
        self.table.blockSignals(True);row=self.table.rowCount();self.table.insertRow(row)
        self.records.append(record);self.original.append(dict(values))
        for col,(key,_) in enumerate(self.fields):self.table.setItem(row,col,QTableWidgetItem(values.get(key,'')))
        self.table.setItem(row,len(self.fields),QTableWidgetItem(''))
        self.render_state(row);self.table.blockSignals(False)
        if payload is not None:self.dirty=True;self.original[row]={}

    def payload(self,row):return {key:self.table.item(row,col).text().strip() for col,(key,_) in enumerate(self.fields)}

    def render_state(self,row):
        record=self.records[row];posted=bool(record and record['operation_id'] is not None)
        message='Registrada · #'+str(record['operation_id']) if posted else ('Pendiente de completar · '+record['error'] if record else 'Sin guardar')
        status=self.table.item(row,len(self.fields));status.setText(message);status.setToolTip(message)
        status.setFlags(status.flags() & ~Qt.ItemIsEditable)
        for col in range(self.table.columnCount()):
            item=self.table.item(row,col);item.setToolTip(message)
            if posted:item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setForeground(QColor('#137844' if posted else '#ac2938' if record else '#183052'))
            item.setBackground(QColor('#f0faf4' if posted else '#fff0f1' if record else '#ffffff'))

    def _edited(self,item):
        self.dirty=True
        if item.column()<len(self.fields):
            self.table.blockSignals(True);self.table.item(item.row(),len(self.fields)).setText('Cambios sin guardar');self.table.blockSignals(False)

    def duplicate(self):
        row=self.table.currentRow()
        if row>=0:self.add_row(payload=self.payload(row));self.table.setCurrentCell(self.table.rowCount()-1,0)

    def remove_rows(self):
        rows=sorted({i.row() for i in self.table.selectedIndexes()},reverse=True)
        if not rows:return
        if any(self.records[r] for r in rows):
            if QMessageBox.question(self,'Quitar pendientes','¿Quitar las filas pendientes seleccionadas? Las operaciones ya registradas se conservan.')!=QMessageBox.Yes:return
        for row in rows:
            record=self.records[row]
            if record and record['operation_id'] is not None:continue
            try:
                if record:self.repository.discard(record['id'],record['revision']);self.saved.emit()
            except StorageError as exc:self.status.setText(str(exc));continue
            self.table.removeRow(row);self.records.pop(row);self.original.pop(row)
        self.dirty=True

    def paste(self):
        text=QApplication.clipboard().text()
        if not text:return
        values=list(csv.reader(io.StringIO(text),delimiter='\t'))
        start=max(0,self.table.currentRow());column=max(0,self.table.currentColumn())
        if column>=len(self.fields):column=0
        if len(values)>500 or any(len(v)+column>len(self.fields) for v in values):
            self.status.setText('Pega hasta 500 filas y solo las columnas de datos, en el orden de los encabezados.');return
        for offset,cells in enumerate(values):
            row=start+offset
            while row>=self.table.rowCount():self.add_row()
            if self.records[row] and self.records[row]['operation_id'] is not None:
                self.status.setText('No se puede pegar sobre filas registradas. Agrega filas nuevas.');return
        for offset,cells in enumerate(values):
            for j,value in enumerate(cells):self.table.item(start+offset,column+j).setText(value)

    def persist(self,checked=False,*,retry=False):
        self.save_button.setFocus()  # Commit any active cell editor before reading.
        posted=pending=0;failed=False;errors=[]
        self.save_button.setEnabled(False)
        try:
            for row in range(self.table.rowCount()):
                record=self.records[row];payload=self.payload(row)
                if record and record['operation_id'] is not None:continue
                unchanged=payload=={key:self.original[row].get(key,'') for key,_ in self.fields}
                if not record and (unchanged or not any(payload.values())):continue
                if record and unchanged and not retry:continue
                try:
                    result=self.repository.save(self.kind,payload,record['id'] if record else None,record['revision'] if record else None)
                except StorageError as exc:
                    errors.append(f'Fila {row+1}: {exc}');failed=True;continue
                self.records[row]=result;self.original[row]=payload
                self.table.blockSignals(True);self.render_state(row);self.table.blockSignals(False)
                if result['operation_id'] is None:pending+=1
                else:posted+=1
            self.show_row_details(self.table.currentRow())
            self.dirty=failed
            self.status.setText(f'{posted} registradas · {pending} pendientes guardadas.'+(' No se guardaron: '+' · '.join(errors) if failed else ' Puedes cerrar y retomarlas desde Movimientos.'))
            self.saved.emit()
        finally:self.save_button.setEnabled(True)

    def reject(self):
        if self.dirty and QMessageBox.question(self,'Cambios sin guardar','¿Cerrar sin guardar los cambios de las filas?')!=QMessageBox.Yes:return
        super().reject()

    def closeEvent(self,event):
        if self.dirty:
            event.ignore();self.reject()
        else:super().closeEvent(event)


class PendingEntries(QWidget):
    open_requested=Signal(str)
    def __init__(self,connection,kind,parent=None):
        super().__init__(parent);self.repository=QuickEntriesRepository(connection);self.kind=kind;self.rows=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.title=note('Pendientes de completar · Todos los períodos (fuera de los totales)','error');layout.addWidget(self.title)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['Fecha','Cliente / concepto','Por completar · doble clic para editar'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setMaximumHeight(170)
        layout.addWidget(self.table);self.table.cellDoubleClicked.connect(lambda row,col:self.open_requested.emit(self.rows[row]['id']))
        self.refresh()
    def refresh(self):
        self.rows=self.repository.pending(self.kind);self.table.setRowCount(len(self.rows));self.setVisible(bool(self.rows))
        self.title.setText(f'Pendientes de completar: {len(self.rows)} · Todos los períodos · Fuera de los totales')
        for i,row in enumerate(self.rows):
            p=row['payload']
            for j,text in enumerate([p.get('date',''),p.get('customer',p.get('concept','')) or 'Sin nombre',row['error']]):
                item=QTableWidgetItem(text);item.setForeground(QColor('#ac2938'));item.setBackground(QColor('#fff0f1'));item.setToolTip(text);self.table.setItem(i,j,item)
