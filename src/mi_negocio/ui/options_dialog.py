"""Edición de las listas compartidas del catálogo."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QListWidget, QLineEdit, QPushButton

from .form_validation import check, required
from ..repository import StorageError


class OptionsDialog(QDialog):
    renamed = Signal(str, str, str)

    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle('Editar listas del catálogo')
        self.setMinimumSize(400, 400)
        self.resize(460, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.group = QComboBox()
        self.group.addItem('Marcas / proveedores', 'brand')
        self.group.addItem('Subtipos', 'subtype')
        self.group.setAccessibleName('Lista que deseas editar')
        layout.addWidget(self.group)
        hint = QLabel('Selecciona una opción para cambiar su nombre. El cambio se aplica a todos los productos asociados.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.options = QListWidget()
        self.options.setAccessibleName('Opciones existentes')
        layout.addWidget(self.options, 1)
        self.name = QLineEdit()
        self.name.setPlaceholderText('Nombre de la opción')
        self.name.setAccessibleName('Nombre de la opción')
        layout.addWidget(self.name)
        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        self.add_button = QPushButton('Agregar nueva')
        self.rename_button = QPushButton('Renombrar selección')
        actions.addWidget(self.add_button)
        actions.addWidget(self.rename_button)
        layout.addLayout(actions)
        close = QPushButton('Cerrar')
        for button in (self.add_button, self.rename_button, close):
            button.setAutoDefault(False)
        self.name.returnPressed.connect(lambda: self.rename() if self.options.selectedItems() else self.add())
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.group.currentIndexChanged.connect(self.reload)
        self.options.currentTextChanged.connect(self.name.setText)
        self.options.itemSelectionChanged.connect(lambda: self.rename_button.setEnabled(bool(self.options.selectedItems())))
        self.add_button.clicked.connect(self.add)
        self.rename_button.clicked.connect(self.rename)
        self.reload()

    def reload(self):
        self.error.clear()
        self.options.clear()
        self.name.clear()
        self.rename_button.setEnabled(False)
        try:
            self.options.addItems(self.repository.list_options(self.group.currentData()))
        except StorageError as error:
            self.error.setText(str(error))

    def add(self):
        if not check(self,[required(self.name,'el nombre')],self.error):return
        try:
            self.repository.add_option(self.group.currentData(), self.name.text())
        except StorageError as error:
            self.error.setText(str(error))
            return
        self.reload()

    def rename(self):
        selected = self.options.currentItem()
        if not selected:
            return
        if not check(self,[required(self.name,'el nombre')],self.error):return
        group, old, new = self.group.currentData(), selected.text(), self.name.text().strip()
        try:
            self.repository.rename_option(group, old, new)
        except StorageError as error:
            self.error.setText(str(error))
            return
        self.renamed.emit(group, old, new)
        self.reload()
