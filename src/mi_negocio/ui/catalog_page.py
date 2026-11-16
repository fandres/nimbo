from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHeaderView, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..repository import CatalogRepository, DuplicateCodeError, StorageError
from .product_dialog import ProductDialog
from .options_dialog import OptionsDialog
from .style import STYLE, format_cop


class CatalogPage(QWidget):
    def __init__(self, repository: CatalogRepository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.products = []
        self.dialog = None
        self.setStyleSheet(STYLE)
        main = QVBoxLayout(self)
        main.setContentsMargins(28, 30, 28, 18)
        main.setSpacing(12)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.addWidget(self._label('TU NEGOCIO, EN ORDEN', 'eyebrow'))
        title = self._label('Catálogo de productos', 'heading')
        title.setWordWrap(True)
        heading.addWidget(title)
        subtitle = self._label('Agrega y organiza los productos y servicios que ofreces.', 'subtitle')
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        self.new_button = QPushButton('+  Agregar al catálogo')
        self.new_button.setObjectName('primary')
        self.new_shortcut = QShortcut(QKeySequence('Ctrl+N'), self)
        self.new_shortcut.setContext(Qt.WindowShortcut)
        self.new_shortcut.activated.connect(self._new)
        self.new_button.setToolTip('Agregar un producto o servicio al catálogo (Ctrl+N)')
        header.addWidget(self.new_button)
        main.addLayout(header)
        card = QFrame()
        card.setObjectName('card')
        content = QVBoxLayout(card)
        content.setContentsMargins(18, 18, 18, 12)
        content.setSpacing(10)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Buscar por código o nombre…')
        self.search.setAccessibleName('Buscar por código o nombre')
        self.search.setClearButtonEnabled(True)
        self.kind_filter = QComboBox()
        self.kind_filter.setAccessibleName('Filtrar por tipo')
        for name, value in [('Todos los tipos', None), ('Productos', 'product'), ('Servicios', 'service')]:
            self.kind_filter.addItem(name, value)
        self.active_filter = QComboBox()
        self.active_filter.setAccessibleName('Filtrar por estado')
        for name, value in [('Todos los estados', None), ('Activos', True), ('Inactivos', False)]:
            self.active_filter.addItem(name, value)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.kind_filter)
        filters.addWidget(self.active_filter)
        content.addLayout(filters)
        classifications = QHBoxLayout()
        self.brand_filter, self.subtype_filter = QComboBox(), QComboBox()
        self.brand_filter.setAccessibleName('Filtrar por marca o proveedor')
        self.subtype_filter.setAccessibleName('Filtrar por subtipo')
        self.brand_filter.addItem('Todas las marcas / proveedores', None)
        self.subtype_filter.addItem('Todos los subtipos', None)
        classifications.addWidget(self.brand_filter, 1)
        classifications.addWidget(self.subtype_filter, 1)
        self.lists_button = QPushButton('Editar listas')
        self.lists_button.clicked.connect(self._manage_lists)
        classifications.addWidget(self.lists_button)
        content.addLayout(classifications)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['Código', 'Nombre', 'Tipo', 'Precio recomendado · COP', 'Estado', 'Marca / proveedor', 'Subtipo'])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(70)
        content.addWidget(self.table, 1)
        self.empty_label = QLabel()
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setObjectName('muted')
        content.addWidget(self.empty_label, 1)
        self.clear_button = QPushButton('Limpiar filtros')
        self.clear_button.clicked.connect(self._clear_filters)
        content.addWidget(self.clear_button, alignment=Qt.AlignCenter)
        self.empty_new = QPushButton('Agregar mi primer producto')
        self.empty_new.setObjectName('primary')
        self.empty_new.clicked.connect(self._new)
        content.addWidget(self.empty_new, alignment=Qt.AlignCenter)
        footer = QHBoxLayout()
        self.count_label = self._label('', 'muted')
        footer.addWidget(self.count_label, 1)
        self.edit_button = QPushButton('Editar')
        self.edit_button.setObjectName('catalogEdit')
        self.active_button = QPushButton('Desactivar')
        footer.addWidget(self.edit_button)
        footer.addWidget(self.active_button)
        content.addLayout(footer)
        main.addWidget(card, 1)
        self.notice = self._label('', 'notice')
        self.notice.setWordWrap(True)
        main.addWidget(self.notice)
        foot = self._label('Selecciona una fila para editar o desactivar. Desactivar conserva su información.\nActivo indica que ofreces el producto o servicio; no representa existencias.', 'muted')
        foot.setWordWrap(True)
        main.addWidget(foot)
        self.new_button.clicked.connect(self._new)
        self.edit_button.clicked.connect(self._edit)
        self.active_button.clicked.connect(self._toggle_active)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.cellDoubleClicked.connect(lambda *_: self._edit())
        self.search.textChanged.connect(self.refresh_products)
        self.kind_filter.currentIndexChanged.connect(self.refresh_products)
        self.active_filter.currentIndexChanged.connect(self.refresh_products)
        self.brand_filter.currentIndexChanged.connect(self.refresh_products)
        self.subtype_filter.currentIndexChanged.connect(self.refresh_products)
        self.refresh_products()

    def _refresh_options(self):
        # Fetch both lists first; preserve the current filters if storage fails.
        values = [(self.brand_filter, 'Todas las marcas / proveedores', self.repository.list_options('brand')),
                  (self.subtype_filter, 'Todos los subtipos', self.repository.list_options('subtype'))]
        for combo, title, names in values:
            selected = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(title, None)
            for name in names:
                combo.addItem(name, name)
            combo.setCurrentIndex(max(0, combo.findData(selected)))
            combo.blockSignals(False)

    def _manage_lists(self):
        dialog = OptionsDialog(self.repository, self)
        self.lists_dialog = dialog
        def renamed(group, old, new):
            combo = self.brand_filter if group == 'brand' else self.subtype_filter
            index = combo.findData(old)
            if index >= 0:
                combo.setItemData(index, new)
                combo.setItemText(index, new)
        dialog.renamed.connect(renamed)
        dialog.finished.connect(self.refresh_products)
        dialog.open()

    @staticmethod
    def _label(text, name):
        label = QLabel(text)
        label.setObjectName(name)
        return label

    def _selected(self):
        row = self.table.currentRow()
        return self.products[row] if self.table.selectionModel().hasSelection() and 0 <= row < len(self.products) else None

    def _update_actions(self):
        product = self._selected()
        self.edit_button.setEnabled(product is not None)
        self.active_button.setEnabled(product is not None)
        self.active_button.setText('Activar' if product and not product.active else 'Desactivar')
        self.active_button.setObjectName('catalogActivate' if product and not product.active else 'catalogDeactivate')
        self.active_button.style().unpolish(self.active_button)
        self.active_button.style().polish(self.active_button)
        self.active_button.update()

    def refresh_products(self, *_):
        selected = self._selected()
        try:
            self._refresh_options()
            products = self.repository.list_products(self.search.text(), self.kind_filter.currentData(), self.active_filter.currentData(), self.brand_filter.currentData(), self.subtype_filter.currentData())
        except StorageError as error:
            self.notice.setText(str(error))
            return False
        self.notice.clear()
        self.products = products
        self.table.setRowCount(0)
        for row, product in enumerate(products):
            self.table.insertRow(row)
            cells = [product.code, product.name, 'Producto' if product.kind == 'product' else 'Servicio',
                     format_cop(product.price_cop_cents), 'Activo' if product.active else 'Inactivo', product.brand or '—', product.subtype or '—']
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if column == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if column == 4:
                    item.setForeground(QColor('#287354' if product.active else '#7b8494'))
                self.table.setItem(row, column, item)
        if selected:
            for row, product in enumerate(products):
                if product.id == selected.id:
                    self.table.selectRow(row)
                    break
        filtered = bool(self.search.text() or self.kind_filter.currentIndex() or self.active_filter.currentIndex() or self.brand_filter.currentIndex() or self.subtype_filter.currentIndex())
        empty = not products
        self.table.setVisible(not empty)
        self.empty_label.setVisible(empty)
        self.empty_label.setText('No encontramos resultados.\nPrueba otra búsqueda o limpia los filtros.' if filtered else 'Tu catálogo empieza aquí\n\nAgrega tu primer producto o servicio.')
        self.clear_button.setVisible(empty and filtered)
        self.empty_new.setVisible(empty and not filtered)
        self.count_label.setText(f'{len(products)} registro' + ('' if len(products) == 1 else 's'))
        self._update_actions()
        return True

    def _clear_filters(self):
        self.search.clear()
        self.kind_filter.setCurrentIndex(0)
        self.active_filter.setCurrentIndex(0)
        self.brand_filter.setCurrentIndex(0)
        self.subtype_filter.setCurrentIndex(0)

    def _new(self):
        self._open_dialog()

    def _edit(self):
        if product := self._selected():
            self._open_dialog(product)

    def _open_dialog(self, product=None):
        try:
            dialog = ProductDialog(self, product, self.repository.list_options('brand'), self.repository.list_options('subtype'))
        except StorageError as error:
            self.notice.setText(str(error))
            return
        self.dialog = dialog

        def check_code():
            code = dialog.code.text()
            if self.repository.connection is None or not dialog.isVisible() or not code or dialog.cancel_button.hasFocus():
                return
            try:
                duplicate = self.repository.code_exists(code, product.id if product else None)
            except StorageError as error:
                dialog.general_error.setText(str(error))
                dialog.general_error.show()
                return
            if duplicate:
                errors = {key: label.text() for key, label in dialog.errors.items() if not label.isHidden()}
                errors['code'] = 'Este código ya existe. Usa otro o edita el registro existente.'
                dialog.show_errors(errors)

        def clear_code_error():
            from .form_validation import clear_field
            dialog.errors['code'].clear()
            dialog.errors['code'].hide()
            clear_field(dialog.code)

        dialog.code.editingFinished.connect(check_code)
        dialog.code.textChanged.connect(clear_code_error)

        def persist(data):
            try:
                saved = self.repository.update(product.id, data) if product else self.repository.create(data)
            except DuplicateCodeError as error:
                dialog.show_errors({'code': str(error)})
                return
            except StorageError as error:
                dialog.general_error.setText(str(error))
                dialog.general_error.show()
                return
            dialog.accept()
            if self.refresh_products():
                visible = any(p.id == saved.id for p in self.products)
                self.notice.setText('Registro guardado.' if visible else 'Registro guardado. No aparece porque no coincide con los filtros actuales.')
                for row, p in enumerate(self.products):
                    if p.id == saved.id:
                        self.table.selectRow(row)
                        break

        dialog.save_requested.connect(persist)
        dialog.open()

    def _toggle_active(self):
        product = self._selected()
        if not product:
            return
        if product.active:
            box = QMessageBox(self)
            box.setWindowTitle('Desactivar registro')
            box.setText(f'¿Desactivar «{product.name}»?')
            box.setInformativeText('Conservarás su información y podrás volver a activarlo.')
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText('Desactivar')
            box.button(QMessageBox.No).setText('Cancelar')
            box.setDefaultButton(QMessageBox.No)
            if box.exec() != QMessageBox.Yes:
                return
        try:
            self.repository.set_active(product.id, not product.active)
        except StorageError as error:
            self.notice.setText(str(error))
            return
        if self.refresh_products():
            self.notice.setText('Registro desactivado. Puedes recuperarlo con el filtro Inactivos.' if product.active else 'Registro activado.')
