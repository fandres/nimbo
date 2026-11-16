from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QScrollArea, QFrame, QWidget, QGridLayout,
)

from .form_validation import check
from ..catalog import Product, ProductInput, ValidationError, validate_product


class ProductDialog(QDialog):
    save_requested = Signal(object)

    def __init__(self, parent=None, product: Product | None = None, brands=(), subtypes=()):
        super().__init__(parent)
        self.setWindowTitle('Editar registro' if product else 'Nuevo producto o servicio')
        self.setMinimumWidth(760)
        self.setMinimumHeight(320)
        self.setModal(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        form = QWidget()
        scroll.setWidget(form)
        outer.addWidget(scroll, 1)
        layout = QVBoxLayout(form)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)
        title = QLabel('Editar registro' if product else 'Agrega a tu catálogo')
        title.setObjectName('brand')
        layout.addWidget(title)
        hint = QLabel('Usa el mismo código de tu plataforma de facturación.')
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(12)
        self.code, self.name, self.price = QLineEdit(), QLineEdit(), QLineEdit()
        self.code.setPlaceholderText('Ej. 010')
        self.name.setPlaceholderText('Nombre del producto o servicio')
        self.price.setPlaceholderText('Ej. 1500000,00')
        self.kind = QComboBox()
        self.kind.addItem('Producto', 'product')
        self.kind.addItem('Servicio', 'service')
        self.brand, self.subtype = QComboBox(), QComboBox()
        for combo, names in [(self.brand, brands), (self.subtype, subtypes)]:
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.addItem('')
            combo.addItems(names)
            combo.lineEdit().setPlaceholderText('Selecciona o escribe una opción nueva')
        self.errors = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        for index, (key, label, field) in enumerate((
            ('code', 'Código existente', self.code), ('name', 'Nombre', self.name),
            ('kind', 'Tipo', self.kind),
            ('subtype', 'Subtipo · opcional', self.subtype),
            ('brand', 'Marca / proveedor · opcional', self.brand),
            ('price', 'Precio de venta recomendado · COP', self.price),
        )):
            cell = QVBoxLayout()
            cell.setSpacing(6)
            grid.addLayout(cell, index // 2, index % 2)
            caption = QLabel(label)
            caption.setBuddy(field)
            cell.addWidget(caption)
            field.setAccessibleName(label)
            cell.addWidget(field)
            error = QLabel()
            error.setObjectName('error')
            error.setWordWrap(True)
            error.hide()
            cell.addWidget(error)
            self.errors[key] = error
        helper = QLabel('Sin separadores de miles. Puedes usar coma o punto decimal.')
        helper.setObjectName('muted')
        helper.setWordWrap(True)
        layout.addWidget(helper)
        list_hint = QLabel('Las opciones nuevas se añaden a tus listas al guardar. Puedes renombrarlas desde «Editar listas» en el catálogo.')
        list_hint.setWordWrap(True)
        list_hint.setObjectName('muted')
        layout.addWidget(list_hint)
        self.active = QCheckBox('Activo en el catálogo')
        self.active.setChecked(True)
        layout.addSpacing(8)
        layout.addWidget(self.active)
        self.general_error = QLabel()
        self.general_error.setObjectName('error')
        self.general_error.setWordWrap(True)
        self.general_error.hide()
        layout.addWidget(self.general_error)
        footer = QWidget()
        buttons = QHBoxLayout(footer)
        buttons.setContentsMargins(28, 14, 28, 20)
        buttons.addStretch()
        self.cancel_button = QPushButton('Cancelar')
        self.save_button = QPushButton('Guardar')
        self.save_button.setObjectName('primary')
        self.save_button.setDefault(True)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout.addStretch()
        outer.addWidget(footer)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._validate)
        if product:
            self.brand.setEditText(product.brand)
            self.subtype.setEditText(product.subtype)
            self.code.setText(product.code)
            self.name.setText(product.name)
            self.kind.setCurrentIndex(self.kind.findData(product.kind))
            whole, fraction = divmod(product.price_cop_cents, 100)
            self.price.setText(f'{whole},{fraction:02d}')
            self.active.setChecked(product.active)
        self.code.setFocus()
        self.resize(820, min(560, self.screen().availableGeometry().height() - 100))
        fields = (self.code, self.name, self.kind, self.subtype, self.brand, self.price, self.active, self.cancel_button, self.save_button)
        for first, second in zip(fields, fields[1:]):
            self.setTabOrder(first, second)

    def product_input(self) -> ProductInput:
        return ProductInput(self.code.text(), self.name.text(), self.kind.currentData(),
                            self.price.text(), self.active.isChecked(), self.brand.currentText(), self.subtype.currentText())

    def show_errors(self, errors: dict[str, str]):
        for key, label in self.errors.items():
            label.setText(errors.get(key, ''))
            label.setVisible(key in errors)
            field = getattr(self, key)
            field.setProperty('invalid', key in errors)
            field.style().unpolish(field)
            field.style().polish(field)
        check(self,[(getattr(self,key),message) for key,message in errors.items()])

    def _validate(self):
        self.general_error.clear()
        self.general_error.hide()
        self.show_errors({})
        try:
            data = validate_product(self.product_input())
        except ValidationError as error:
            self.show_errors(error.errors)
            return
        self.save_requested.emit(data)
