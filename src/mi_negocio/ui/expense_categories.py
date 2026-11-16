"""La misma lista de categorías en Configuración y en Nuevo gasto."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QListWidget,QLineEdit,QCheckBox,QPushButton,QDialog
from .form_validation import check, required
from ..storage import StorageError
from .sales_widgets import note


class ExpenseCategoriesEditor(QWidget):
    changed=Signal()
    def __init__(self,repository,parent=None):
        super().__init__(parent);self.repository=repository;self.key=None;self.rows=[]
        root=QVBoxLayout(self)
        root.addWidget(note('Categorías de gastos','cardTitle'))
        root.addWidget(note('Personaliza tus categorías. Desactivar conserva los gastos y permite seguir consultándolos. Comisiones, envíos e intereses de préstamos se identifican por su origen.'))
        self.list=QListWidget();root.addWidget(self.list,1)
        self.name=QLineEdit();self.name.setPlaceholderText('Nombre de la categoría');root.addWidget(self.name)
        self.enabled=QCheckBox('Habilitada');self.enabled.setChecked(True);root.addWidget(self.enabled)
        row=QHBoxLayout();new=QPushButton('Crear nueva');save=QPushButton('Guardar categoría');save.setObjectName('primary');row.addWidget(new);row.addWidget(save);root.addLayout(row)
        self.error=note('','error');root.addWidget(self.error)
        self.list.currentRowChanged.connect(self.select);new.clicked.connect(self.clear);save.clicked.connect(self.persist);self.refresh()

    def refresh(self):
        try:
            rows=self.repository.categories(True);self.list.blockSignals(True);self.list.clear();self.rows=rows
            for row in rows:self.list.addItem(row['name']+('' if row['enabled'] else ' · Deshabilitada'))
            self.list.blockSignals(False)
        except StorageError as e:self.error.setText(str(e))

    def select(self,index):
        if 0<=index<len(self.rows):
            row=self.rows[index];self.key=row['id'];self.name.setText(row['name']);self.enabled.setChecked(bool(row['enabled']))

    def clear(self):
        self.list.setCurrentRow(-1);self.key=None;self.name.clear();self.enabled.setChecked(True);self.error.clear();self.name.setFocus()

    def persist(self):
        issues=[required(self.name,'el nombre')]
        if not check(self,issues,self.error):return
        try:
            key=self.repository.save_category(self.key,self.name.text(),self.enabled.isChecked());self.refresh()
            self.list.setCurrentRow(next(i for i,r in enumerate(self.rows) if r['id']==key));self.error.clear();self.changed.emit()
        except StorageError as e:self.error.setText(str(e))


def edit_categories(repository,parent):
    dialog=QDialog(parent);dialog.setWindowTitle('Categorías de gastos · Nimbo');dialog.resize(580,480)
    box=QVBoxLayout(dialog);box.addWidget(ExpenseCategoriesEditor(repository));close=QPushButton('Cerrar');close.clicked.connect(dialog.accept);box.addWidget(close);dialog.exec()
