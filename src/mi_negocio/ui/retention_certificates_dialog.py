"""Annual certificate states, edited without changing financial operations."""
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QTableWidget,QTableWidgetItem,
    QHeaderView,QComboBox,QLineEdit,QPushButton,QTextEdit,QMessageBox)
from ..retention_certificates import STATUSES
from ..attachments import AttachmentsRepository
from .attachments_dialog import AttachmentsDialog
from .icons import icon
from ..storage import StorageError
from .sales_widgets import note
from .style import STYLE,format_cop


class RetentionCertificatesDialog(QDialog):
    def __init__(self,repository,groups,parent=None):
        super().__init__(parent)
        self.repository=repository;self.groups=[dict(g) for g in groups]
        self.setWindowTitle('Certificados de retención · Nimbo');self.setStyleSheet(STYLE)
        self.resize(1160,520)
        layout=QVBoxLayout(self)
        layout.addWidget(note('Certificados por cliente y año','cardTitle'))
        layout.addWidget(note('El estado corresponde al año completo. Los importes corresponden al filtro del informe. El estado se guarda al elegirlo y la nota al salir del campo.'))
        self.table=QTableWidget(len(groups),7)
        self.table.setHorizontalHeaderLabels(['Año','Cliente / identificación','Retención del período','Certificado anual','Nota opcional','Historial','Soportes'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(60);layout.addWidget(self.table,1)
        self.error=note('','error');layout.addWidget(self.error)
        self.document_buttons=[]
        for index,g in enumerate(self.groups):
            for col,text in enumerate([str(g['year']),g['name']+'\n'+(g['identification'] or 'Sin documento: revisar identidad'),format_cop(g['withholding_cents'])]):
                item=QTableWidgetItem(text);item.setToolTip(text);self.table.setItem(index,col,item)
            state=QComboBox()
            for value,label in STATUSES.items():state.addItem(label,value)
            state.setMinimumWidth(state.fontMetrics().horizontalAdvance(max(STATUSES.values(),key=len))+64)
            state.setCurrentIndex(state.findData(g['status']));state.setAccessibleName('Certificado de '+g['name'])
            comment=QLineEdit(g['note']);comment.setMaxLength(2000);comment.setPlaceholderText('Detalle para recordar')
            history=QPushButton('Ver');history.setAutoDefault(False)
            self.table.setCellWidget(index,3,state);self.table.setCellWidget(index,4,comment);self.table.setCellWidget(index,5,history)
            state.activated.connect(lambda _=None,i=index:self.save(i))
            comment.editingFinished.connect(lambda i=index:self.save(i))
            history.clicked.connect(lambda _=False,i=index:self.history(i))
            documents=QPushButton();documents.setIcon(icon('attachment',size=18));documents.setAutoDefault(False)
            documents.setAccessibleName('Documentos del certificado de '+g['name']+' '+str(g['year']))
            documents.clicked.connect(lambda _=False,i=index:self.documents(i))
            self.document_buttons.append(documents);self.table.setCellWidget(index,6,documents)
            self.refresh_documents(index)
        close=QPushButton('Cerrar');close.clicked.connect(self.accept);layout.addWidget(close)

    def save(self,index):
        g=self.groups[index];state=self.table.cellWidget(index,3);comment=self.table.cellWidget(index,4)
        if (state.currentData(),comment.text().strip())==(g['status'],g['note']):return
        try:
            revision=self.repository.save(g['year'],g['customer_key'],state.currentData(),comment.text(),expected_revision=g['revision'])
            g.update(status=state.currentData(),note=comment.text().strip(),revision=revision)
            self.error.clear()
            return True
        except StorageError as exc:
            with QSignalBlocker(state):state.setCurrentIndex(state.findData(g['status']))
            self.error.setText(str(exc)+' La nota sigue disponible para copiarla si necesitas volver a abrir.')
            return False

    def refresh_documents(self,index):
        g=self.groups[index];button=self.document_buttons[index]
        try:
            key=self.repository.document_owner(g['year'],g['customer_key'],create=False)
            count=len(AttachmentsRepository(self.repository.connection).list('retention_certificate',key)) if key else 0
            button.setText(str(count) if count else '')
            button.setToolTip(f'{count} documentos. Adjuntar o consultar el certificado anual.')
        except StorageError as exc:self.error.setText(str(exc))

    def documents(self,index):
        g=self.groups[index]
        try:key=self.repository.document_owner(g['year'],g['customer_key'])
        except StorageError as exc:self.error.setText(str(exc));return
        dialog=AttachmentsDialog(self.repository.connection,'retention_certificate',key,self)
        dialog.setWindowTitle(f"Certificado {g['year']} · {g['name']}")
        dialog.documents_changed.connect(lambda:self.refresh_documents(index))
        dialog.files_added.connect(lambda _:self.offer_received(index,dialog))
        dialog.show()
        return dialog

    def offer_received(self,index,parent):
        g=self.groups[index]
        if g['status']=='received':return
        if QMessageBox.question(parent,'Certificado adjuntado',
            f"Se guardó la copia. ¿Marcar el certificado de {g['name']} del año {g['year']} como recibido?",
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        state=self.table.cellWidget(index,3)
        with QSignalBlocker(state):state.setCurrentIndex(state.findData('received'))
        if self.save(index) is False:
            parent.error.setText('La copia se guardó, pero no se pudo cambiar el estado. '+self.error.text())

    def history(self,index):
        g=self.groups[index]
        try:rows=self.repository.history(g['year'],g['customer_key'])
        except StorageError as exc:self.error.setText(str(exc));return
        dialog=QDialog(self);dialog.setWindowTitle('Historial del certificado');dialog.resize(600,380)
        layout=QVBoxLayout(dialog);text=QTextEdit();text.setReadOnly(True)
        text.setPlainText('\n\n'.join(r['changed_at']+'\n'+STATUSES[r['status']]+'\n'+r['note'] for r in rows) or 'Sin cambios registrados.')
        layout.addWidget(text);close=QPushButton('Cerrar');close.clicked.connect(dialog.accept);layout.addWidget(close);dialog.show()
