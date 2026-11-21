"""Gestión compartida de documentos de registros guardados."""
from PySide6.QtCore import Qt,QUrl,Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QPushButton,QFileDialog,QMessageBox,QWidget
from ..attachments import AttachmentsRepository, allowed_extensions
from ..storage import StorageError
from .icons import icon
from .sales_widgets import note
from .style import STYLE


class AttachmentsDialog(QDialog):
    files_added=Signal(int)
    documents_changed=Signal()
    def __init__(self,connection,kind,key,parent=None):
        super().__init__(parent);self.repo=AttachmentsRepository(connection);self.kind=kind;self.key=key
        self.setWindowTitle('Documentos adjuntos');self.setStyleSheet(STYLE);self.resize(620,380)
        layout=QVBoxLayout(self);layout.addWidget(note('Documentos adjuntos','cardTitle'))
        if kind=='retention_certificate':
            layout.addWidget(note('Copias del certificado en Documentos, organizadas por año y cliente. Se conserva el original.'))
            layout.addWidget(note('Adjunta el certificado en PDF, PNG o JPG.'))
        else:
            layout.addWidget(note('Se guarda una copia en Documentos, por año y mes del registro. El original se conserva.'))
            layout.addWidget(note('Factura electrónica PDF/XML o comprobante PNG/JPG. El XML se conserva como documento; no rellena datos automáticamente.'))
        self.files=QListWidget();layout.addWidget(self.files,1)
        row=QHBoxLayout();layout.addLayout(row)
        for title,callback in [('Adjuntar archivos',self.add),('Abrir',self.open_file),('Ver carpeta',self.open_folder),('Quitar',self.remove)]:
            b=QPushButton(title);b.setAutoDefault(False);b.clicked.connect(callback);row.addWidget(b)
            if title=='Adjuntar archivos':b.setObjectName('primary')
        self.error=note('','error');layout.addWidget(self.error)
        close=QPushButton('Cerrar');close.clicked.connect(self.accept);layout.addWidget(close)
        self.files.itemDoubleClicked.connect(self.open_file);self.refresh()

    def refresh(self):
        self.files.clear()
        try:
            for row in self.repo.list(self.kind,self.key):
                item=QListWidgetItem(row['original_name']);item.setData(Qt.UserRole,row);item.setToolTip(row['relative_path']);self.files.addItem(item)
        except StorageError as error:self.error.setText(str(error))

    def add(self):
        extensions=allowed_extensions(self.kind)
        patterns=' '.join('*'+ext for ext in sorted(extensions))+' '+' '.join('*'+ext.upper() for ext in sorted(extensions))
        paths,_=QFileDialog.getOpenFileNames(self,'Adjuntar documentos','','Documentos ('+patterns+')')
        self.error.clear()
        added=0
        for path in paths:
            try:
                self.repo.add(self.kind,self.key,path);added+=1
            except StorageError as error:
                self.error.setText(str(error)+' Los archivos añadidos anteriormente se conservaron.');break
        self.refresh()
        if added:
            self.documents_changed.emit();self.files_added.emit(added)

    def selected(self):
        item=self.files.currentItem()
        return item.data(Qt.UserRole) if item else None

    def open_file(self,*_):
        row=self.selected()
        if row:self.open_path(row)

    def open_path(self,row,folder=False):
        try:
            path=self.repo.path(row)
            if folder:path=path.parent
            if not path.exists():raise StorageError('No se encuentra la copia del documento en este equipo.')
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):raise StorageError('No se pudo abrir. Revisa el visor predeterminado del sistema.')
            self.error.clear()
        except StorageError as error:self.error.setText(str(error))

    def open_folder(self):
        row=self.selected()
        if row:self.open_path(row,True)
        elif self.files.count():self.open_path(self.files.item(0).data(Qt.UserRole),True)

    def remove(self):
        row=self.selected()
        if not row:return
        if QMessageBox.question(self,'Quitar adjunto','¿Quitar este documento del registro? La copia permanecerá en la carpeta para poder recuperarla.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:self.repo.remove(row['id']);self.refresh();self.documents_changed.emit()
        except StorageError as error:self.error.setText(str(error))


def attachment_button(connection,kind,key,parent=None):
    button=QPushButton(parent);button.setIcon(icon('attachment',size=18));button.setAutoDefault(False)
    button.setAccessibleName('Documentos adjuntos');button.setStyleSheet('padding: 6px; min-width: 28px;')
    def refresh():
        try:
            count=len(AttachmentsRepository(connection).list(kind,key))
            button.setText(str(count) if count else '')
            button.setToolTip(f'Documentos adjuntos: {count}. Adjuntar o consultar copias.')
        except StorageError as error:button.setToolTip(str(error))
    def show():
        dialog=AttachmentsDialog(connection,kind,key,button.window());dialog.exec();refresh()
    button.clicked.connect(show);refresh();return button


def with_attachment(action,connection,kind,key):
    holder=QWidget();layout=QHBoxLayout(holder);layout.setContentsMargins(0,0,0,0);layout.setSpacing(4)
    layout.addWidget(action);layout.addWidget(attachment_button(connection,kind,key,holder))
    return holder
