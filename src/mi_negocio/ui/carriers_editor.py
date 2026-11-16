"""Lista editable de transportadoras, conservando referencias históricas."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QListWidget,QLineEdit,QCheckBox,QPushButton
from .form_validation import check, required
from ..storage import StorageError
from ..catalog import ValidationError
from .sales_widgets import note,error_text


class CarriersEditor(QWidget):
    changed=Signal()
    def __init__(self,repository):
        super().__init__();self.repository=repository;self.key=None;self.rows=[]
        self.setObjectName('settingsEditor');root=QVBoxLayout(self)
        root.addWidget(note('Agrega, renombra o deshabilita transportadoras. Las ventas conservan el nombre original.'))
        self.list=QListWidget();root.addWidget(self.list)
        self.name=QLineEdit();self.name.setPlaceholderText('Nombre de la transportadora');root.addWidget(self.name)
        self.enabled=QCheckBox('Habilitada');self.enabled.setChecked(True);root.addWidget(self.enabled)
        buttons=QHBoxLayout();new=QPushButton('Crear nueva');save=QPushButton('Guardar cambios');save.setObjectName('primary');buttons.addWidget(new);buttons.addWidget(save);root.addLayout(buttons)
        self.error=note('','error');root.addWidget(self.error)
        self.list.currentRowChanged.connect(self.select);new.clicked.connect(self.clear);save.clicked.connect(self.persist);self.refresh()

    def refresh(self):
        try:
            self.rows=self.repository.list_carriers(True);self.list.clear()
            for row in self.rows:self.list.addItem(row['name']+('' if row['enabled'] else ' · Deshabilitada'))
        except StorageError as error:self.error.setText(str(error))

    def select(self,index):
        if 0<=index<len(self.rows):
            row=self.rows[index];self.key=row['id'];self.name.setText(row['name']);self.enabled.setChecked(bool(row['enabled']))

    def clear(self):
        self.list.setCurrentRow(-1);self.key=None;self.name.clear();self.enabled.setChecked(True);self.error.clear();self.name.setFocus()

    def persist(self):
        issues=[required(self.name,'el nombre')]
        if not check(self,issues,self.error):return
        try:
            key=self.repository.save_carrier(self.key,self.name.text(),self.enabled.isChecked())
            self.refresh()
            self.list.setCurrentRow(next(i for i,row in enumerate(self.rows) if row['id']==key))
            self.error.clear();self.changed.emit()
        except (StorageError,ValidationError) as error:self.error.setText(error_text(error))
