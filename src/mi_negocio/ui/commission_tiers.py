"""Editor opcional de umbrales de comisión."""
from decimal import Decimal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QTableWidget,QHeaderView
from ..commissions import CommissionTier,validate_tiers
from ..catalog import ValidationError
from ..sales import money
from .sales_widgets import note,amount,cents_text,error_text
from .form_validation import check,amount_issue,rate_issue


class CommissionTiersDialog(QDialog):
    def __init__(self,tiers,parent=None):
        super().__init__(parent);self.setWindowTitle('Tarifas por monto');self.resize(660,400);self.tiers=tiers
        box=QVBoxLayout(self)
        box.addWidget(note('Cada tarifa aplica al total completo de la venta, incluido el envío.\nDebajo del primer monto se usa la comisión base. El último tramo no tiene límite superior.'))
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Desde · COP','Comisión %','Cargo fijo · COP',''])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(52);box.addWidget(self.table)
        add=QPushButton('+ Agregar tramo');add.clicked.connect(lambda:self.add_row());box.addWidget(add)
        self.error=note('','error');box.addWidget(self.error)
        actions=QHBoxLayout();cancel=QPushButton('Cancelar');cancel.clicked.connect(self.reject);save=QPushButton('Aplicar tarifas');save.setObjectName('primary');save.clicked.connect(self.persist)
        actions.addWidget(cancel);actions.addWidget(save);box.addLayout(actions)
        for tier in tiers:self.add_row(tier)

    def add_row(self,tier=None):
        row=self.table.rowCount();self.table.insertRow(row)
        for col,value in enumerate((cents_text(tier.from_cents) if tier else '0',str(tier.rate_percent) if tier else '0',cents_text(tier.fixed_cents) if tier else '0')):
            editor=amount();editor.setText(value);self.table.setCellWidget(row,col,editor)
        button=QPushButton('Quitar');button.clicked.connect(lambda:self.remove_row(button));self.table.setCellWidget(row,3,button)

    def remove_row(self,button):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row,3) is button:self.table.removeRow(row);break

    def persist(self):
        issues=[]
        for row in range(self.table.rowCount()):
            a,b,c=[self.table.cellWidget(row,col) for col in range(3)]
            issues.extend([amount_issue(a,'Monto desde',True),rate_issue(b,'Comisión',100),amount_issue(c,'Cargo fijo')])
        if not check(self,issues,self.error):return
        try:
            tiers=tuple(sorted((CommissionTier(money(self.table.cellWidget(i,0).text()),Decimal(self.table.cellWidget(i,1).text().replace(',','.')),money(self.table.cellWidget(i,2).text())) for i in range(self.table.rowCount())),key=lambda t:t.from_cents))
            validate_tiers(tiers);self.tiers=tiers;self.accept()
        except ValidationError as e:
            check(self,[(self.table,error_text(e))],self.error)
