"""Seguimiento explícito de costos, independiente de pagos y recepción."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QGridLayout, QComboBox, QCheckBox
from ..purchases import CATEGORIES, COST_STATES, cost_states_complete
from .sales_widgets import note


class PurchaseProgressEditor(QWidget):
    changed=Signal()

    def __init__(self,parent=None,inline=False,categories=None):
        super().__init__(parent)
        self.inline=inline
        layout=QGridLayout(self); layout.setContentsMargins(0,0,0,0)
        self.activate=QCheckBox('Seguimiento por concepto'); layout.addWidget(self.activate,0,0,1,2)
        self.legacy=QComboBox(); self.legacy.addItem('Costos por completar',False); self.legacy.addItem('Costos completos',True)
        layout.addWidget(self.legacy,0,2,1,2)
        self.editors={}; self.labels=[]
        self.categories=dict(CATEGORIES if categories is None else categories)
        for i,(key,label) in enumerate(self.categories.items()):
            title=note(label); combo=QComboBox()
            for text,value in COST_STATES: combo.addItem(text,value)
            layout.addWidget(title,1+i//2*2,i%2*2,1,2); layout.addWidget(combo,2+i//2*2,i%2*2,1,2)
            self.editors[key]=combo; self.labels.append(title); combo.currentIndexChanged.connect(self.changed)
        self.activate.toggled.connect(self._toggle); self.legacy.currentIndexChanged.connect(self.changed)
        self.set_states(None,False)

    def _toggle(self,*args):
        enabled=self.activate.isChecked()
        if enabled: self.activate.setEnabled(False)
        for widget in (*self.editors.values(),*self.labels): widget.setVisible(enabled and not self.inline)
        self.legacy.setVisible(not enabled)
        self.changed.emit()

    def set_states(self,states,legacy_complete=False):
        self.legacy.setCurrentIndex(int(legacy_complete))
        for key,combo in self.editors.items(): combo.setCurrentIndex(combo.findData(states.get(key,'unselected') if states else 'unselected'))
        self.activate.setChecked(states is not None)
        self.activate.setEnabled(states is None)
        self._toggle()

    def states(self):
        return {key:combo.currentData() for key,combo in self.editors.items()} if self.activate.isChecked() else None

    def is_complete(self):
        states=self.states()
        return cost_states_complete(states) if states is not None else bool(self.legacy.currentData())
