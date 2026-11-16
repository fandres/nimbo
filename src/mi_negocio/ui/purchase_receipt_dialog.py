"""Confirmación explícita de entrada completa, independiente de costos y pagos."""
from PySide6.QtCore import Signal,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QTableWidgetItem,QFrame
from ..purchase_allocation import purchase_progress
from ..purchases_repository import draft_from_record
from ..storage import StorageError
from .form_validation import check
from .purchase_cost_editor import table
from .sales_widgets import note,date_edit
from .style import STYLE


class PurchaseReceiptDialog(QDialog):
    saved=Signal(int)

    def __init__(self,purchases,receipts,purchase_id,parent=None):
        super().__init__(parent);self.purchases=purchases;self.receipts=receipts;self.purchase_id=purchase_id
        self.record=purchases.get(purchase_id);self.revision=self.record['revision']
        self.setStyleSheet(STYLE);self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle('Recibir maquinaria · Nimbo');self.resize(800,580)
        root=QVBoxLayout(self);root.addWidget(note('Recibir maquinaria y confirmar stock','cardTitle'))
        root.addWidget(note('Pedido #'+str(purchase_id)+' · '+self.record['supplier']))
        self.lines=table(['Código / modelo','Unidades a recibir']);root.addWidget(self.lines,1)
        self.lines.setRowCount(len(self.record['lines']))
        for i,line in enumerate(self.record['lines']):
            self.lines.setItem(i,0,QTableWidgetItem(line['code']+' · '+line['name']))
            self.lines.setItem(i,1,QTableWidgetItem(str(line['quantity'])))
        dates=QHBoxLayout();dates.addWidget(note('Fecha de recepción'));self.received_on=date_edit();dates.addWidget(self.received_on);dates.addStretch();root.addLayout(dates)
        progress=purchase_progress(draft_from_record(self.record))
        self.warning=QFrame();self.warning.setObjectName('expenseSummary');warning_layout=QVBoxLayout(self.warning)
        warning_layout.addWidget(note('Puedes recibir la maquinaria. Recuerda completar los costos de este pedido.'))
        from ..purchases import categories_for
        details=', '.join(categories_for(draft_from_record(self.record))[key] for key in progress['pending_categories'])
        if not details:details='Revisar costos pendientes' if progress['legacy'] else 'Falta distribuir gastos entre las máquinas'
        warning_layout.addWidget(note(details));root.addWidget(self.warning)
        self.warning.setVisible(progress['state']!='complete')
        root.addWidget(note('Confirma que recibiste todas estas unidades. No reingreses máquinas de compras antiguas que ya vendiste.'))
        root.addWidget(note('Registra entradas de maquinaria; las ventas todavía no descuentan estas entradas. No confirma pagos.'))
        self.error=note('','error');root.addWidget(self.error)
        buttons=QHBoxLayout();buttons.addStretch();cancel=QPushButton('Cancelar');cancel.setAutoDefault(False)
        self.confirm=QPushButton('Confirmar recepción completa');self.confirm.setObjectName('primary');self.confirm.setDefault(True)
        buttons.addWidget(cancel);buttons.addWidget(self.confirm);root.addLayout(buttons)
        cancel.clicked.connect(self.reject);self.confirm.clicked.connect(self.save)
        self.confirm.setEnabled(not self.record['cancelled_at'] and self.record['receipt'] is None)

    def save(self):
        issues=[]
        if self.received_on.date().toString("yyyy-MM-dd")<self.record["purchased_on"]:
            issues.append((self.received_on,"La recepción no puede ser anterior a la compra."))
        if not check(self,issues,self.error):return
        self.confirm.setEnabled(False)
        try:
            self.receipts.receive(self.purchase_id,self.received_on.date().toPython(),expected_revision=self.revision)
            self.saved.emit(self.purchase_id);self.accept()
        except StorageError as error:
            self.error.setText(str(error));self.confirm.setEnabled(True)
