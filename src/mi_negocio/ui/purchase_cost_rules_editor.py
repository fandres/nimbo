"""Configuration of subtype defaults and complete per-product overrides."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                              QCheckBox, QListWidget, QListWidgetItem, QPushButton, QCompleter)
from ..purchase_cost_rules import PurchaseCostRules
from ..purchase_concepts import PurchaseConceptsRepository
from ..storage import StorageError
from .sales_widgets import note


class PurchaseCostRulesEditor(QWidget):
    changed = Signal()

    def __init__(self, connection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.rules = PurchaseCostRules(connection)
        root = QVBoxLayout(self)
        root.addWidget(note('Costos aplicables por subtipo y producto', 'cardTitle'))
        root.addWidget(note('Los productos heredan del subtipo. Puedes definir una selección propia para cada producto. Una selección vacía significa sin costos adicionales.'))
        row = QHBoxLayout()
        self.scope = QComboBox()
        self.scope.addItem('Subtipos', 'subtype'); self.scope.addItem('Excepciones por producto', 'product')
        self.target = QComboBox(); self.target.setEditable(True); self.target.setInsertPolicy(QComboBox.NoInsert)
        self.target.completer().setFilterMode(Qt.MatchContains)
        self.target.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.target.completer().setCompletionMode(QCompleter.PopupCompletion)
        row.addWidget(self.scope); row.addWidget(self.target, 1); root.addLayout(row)
        self.inherit = QCheckBox(); root.addWidget(self.inherit)
        self.list = QListWidget()
        self.list.setStyleSheet('QListWidget { background: white; border: 1px solid #d7dfe9; border-radius: 8px; } QListWidget::item { padding: 8px; }')
        root.addWidget(self.list, 1)
        self.hint = note(''); root.addWidget(self.hint)
        self.save = QPushButton('Guardar aplicación de costos'); self.save.setObjectName('primary'); root.addWidget(self.save)
        self.status = note(''); root.addWidget(self.status)
        self.scope.currentIndexChanged.connect(self.refresh)
        self.target.currentIndexChanged.connect(self.load)
        self.inherit.toggled.connect(self.toggle_inherit)
        self.save.clicked.connect(self.persist)
        self.refresh()

    def refresh(self, *_):
        current = self.target.currentData()
        self.target.blockSignals(True); self.target.clear()
        if self.scope.currentData() == 'product':
            rows = self.connection.execute("SELECT id,code||' · '||name AS label FROM products WHERE kind='product' ORDER BY name").fetchall()
        else:
            rows = self.connection.execute("SELECT id,name AS label FROM catalog_options WHERE group_key='subtype' ORDER BY name").fetchall()
        for row in rows:self.target.addItem(row['label'], row['id'])
        index = self.target.findData(current)
        if index >= 0:self.target.setCurrentIndex(index)
        self.target.blockSignals(False); self.load()

    def inherited_keys(self):
        if self.scope.currentData() == 'product':return self.rules.inherited(self.target.currentData())
        return list(PurchaseConceptsRepository(self.connection).definitions())

    def load(self, *_):
        target = self.target.currentData()
        self.status.clear(); self.list.clear()
        selection = self.rules.selection(self.scope.currentData(), target) if target is not None else None
        self.inherit.blockSignals(True)
        self.inherit.setText('Heredar del subtipo' if self.scope.currentData() == 'product' else 'Usar todos los conceptos activos (predeterminado)')
        self.inherit.setChecked(selection is None); self.inherit.blockSignals(False)
        selected = self.inherited_keys() if selection is None else selection
        for concept in PurchaseConceptsRepository(self.connection).list():
            item = QListWidgetItem(concept['name'] + ('' if concept['enabled'] else ' · desactivado'))
            item.setData(Qt.UserRole, concept['key'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if concept['key'] in selected else Qt.Unchecked)
            self.list.addItem(item)
        self.save.setEnabled(target is not None); self.inherit.setEnabled(target is not None)
        self.list.setEnabled(target is not None and selection is not None)
        self.hint.setText('Los cambios se aplican a compras nuevas. Las guardadas solo cambian al pulsar Actualizar conceptos; sus importes se conservan.')

    def toggle_inherit(self, checked):
        self.list.setEnabled(not checked and self.target.currentData() is not None)
        if checked:
            keys = self.inherited_keys()
            for i in range(self.list.count()):
                item = self.list.item(i); item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in keys else Qt.Unchecked)

    def persist(self):
        if self.target.currentIndex() < 0 or self.target.currentText() != self.target.itemText(self.target.currentIndex()):
            self.status.setText('Selecciona un producto o subtipo de los resultados.'); self.target.setFocus(); return
        selection = None if self.inherit.isChecked() else [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.Checked]
        try:
            self.rules.save(self.scope.currentData(), self.target.currentData(), selection)
            self.status.setText('Aplicación de costos guardada.'); self.changed.emit()
        except StorageError as error:self.status.setText(str(error))
