"""User-facing complete backups. Mutations are blocked while copying."""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from PySide6.QtCore import Qt,Signal,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QCheckBox,
                              QFileDialog,QMessageBox,QApplication,QDialog)
from ..backup_archive import BackupError,create_backup,unpack_backup
from ..backup_restore import prepare_restore
from ..backup_preferences import BackupPreferences
from .sales_widgets import note


class BackupPage(QWidget):
    restore_requested=Signal()

    def __init__(self,connection,parent=None,preferences=None):
        super().__init__(parent);self.connection=connection
        self.preferences=preferences or BackupPreferences();self.busy=False;self.has_unsaved_changes=lambda:False
        root=QVBoxLayout(self)
        root.addWidget(note('Copias de seguridad','cardTitle'))
        root.addWidget(note('Guarda tus registros, documentos adjuntos, logo y preferencias en un solo archivo. El respaldo incluye las copias de documentos conservadas en el historial.'))
        row=QHBoxLayout();self.create=QPushButton('Crear respaldo');self.create.setObjectName('primary')
        self.restore=QPushButton('Restaurar respaldo');self.restore.setObjectName('removeAction')
        row.addWidget(self.create);row.addWidget(self.restore);row.addStretch();root.addLayout(row)
        root.addWidget(note('Respaldos automáticos','cardTitle'))
        self.enabled=QCheckBox('Crear un respaldo al abrir Nimbo, como máximo una vez al día');self.enabled.setChecked(self.preferences.enabled());root.addWidget(self.enabled)
        self.folder_label=note(self.preferences.folder() or 'Carpeta sin seleccionar');root.addWidget(self.folder_label)
        row=QHBoxLayout();self.choose=QPushButton('Elegir carpeta');self.open_folder=QPushButton('Abrir carpeta');row.addWidget(self.choose);row.addWidget(self.open_folder);row.addStretch();root.addLayout(row)
        root.addWidget(note('Recomendado: una unidad distinta para protegerte si falla este equipo. No se eliminan respaldos automáticamente.'))
        self.status=note(self.preferences.status());root.addWidget(self.status)
        self.message=note('');root.addWidget(self.message);root.addStretch()
        self.create.clicked.connect(self.create_manual);self.restore.clicked.connect(self.restore_manual)
        self.choose.clicked.connect(self.select_folder);self.open_folder.clicked.connect(self.open_selected_folder)
        self.enabled.toggled.connect(self.configure)

    def filename(self):return 'Nimbo-respaldo-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:8]+'.zip'

    def configure(self,enabled):
        try:self.preferences.configure(enabled,self.preferences.folder())
        except BackupError as error:
            self.enabled.blockSignals(True);self.enabled.setChecked(self.preferences.enabled());self.enabled.blockSignals(False)
            self.message.setText(str(error))

    def select_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Carpeta de respaldos',self.preferences.folder())
        if folder:
            try:self.preferences.configure(self.enabled.isChecked(),folder);self.folder_label.setText(folder)
            except BackupError as error:self.message.setText(str(error))

    def open_selected_folder(self):
        folder=self.preferences.folder()
        if folder:QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def run_operation(self,callback):
        if self.busy:return False
        self.busy=True;window=self.window();window.setEnabled(False)
        self.message.setText('Procesando y verificando los archivos. Espera a que termine la operación…');self.message.repaint()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            callback();return True
        except (BackupError,OSError) as error:
            self.message.setText(str(error))
            try:self.preferences.failure(str(error))
            except BackupError:pass
            return False
        finally:
            QApplication.restoreOverrideCursor();window.setEnabled(True);self.busy=False
            self.status.setText(self.preferences.status())

    def make_backup(self,path):
        create_backup(self.connection,path,self.preferences.export())
        self.preferences.success(path)
        self.message.setText('Respaldo completo verificado: '+str(path))

    def create_manual(self):
        path,_=QFileDialog.getSaveFileName(self,'Crear respaldo completo',str(Path(self.preferences.folder() or str(Path.home()))/self.filename()),'Respaldo Nimbo (*.zip)')
        if path:self.run_operation(lambda:self.make_backup(Path(path)))

    def automatic_backup(self):
        if not self.preferences.due():return
        if not self.run_operation(lambda:self.make_backup(Path(self.preferences.folder())/self.filename())):
            QMessageBox.warning(self,'Respaldo automático pendiente',self.message.text()+'\nPuedes continuar usando Nimbo y reintentarlo desde Configuración → Copias de seguridad.')

    def restore_manual(self):
        if self.has_unsaved_changes():
            self.message.setText('Hay cambios sin guardar en Configuración. Guárdalos o vuelve a seleccionar el registro para descartarlos antes de restaurar.');return
        if any(isinstance(w,QDialog) and w.isVisible() for w in QApplication.topLevelWidgets()):
            self.message.setText('Cierra los formularios abiertos antes de restaurar; guarda o descarta sus cambios.');return
        path,_=QFileDialog.getOpenFileName(self,'Restaurar respaldo completo','','Respaldo Nimbo (*.zip)')
        if not path:return
        result={}
        def inspect():
            with TemporaryDirectory(prefix='nimbo-inspect-') as temp:
                result.update(unpack_backup(path,Path(temp)/'checked'))
        if not self.run_operation(inspect):return
        count=sum(name.startswith('Documentos/') for name in result['files'])
        text=(f"Respaldo del {result.get('created_at','fecha desconocida')} · Nimbo {result.get('app_version','')}\n"
              f'{count} documentos.\n\nReemplazará los datos actuales; no mezclará registros. Primero se creará una copia completa del estado actual.\nNimbo se cerrará al finalizar y tendrás que volver a abrirlo.\n\n¿Restaurar este respaldo?')
        if QMessageBox.question(self,'Confirmar restauración',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        if self.run_operation(lambda:prepare_restore(self.connection,path,self.preferences.export())):
            self.restore_requested.emit()
