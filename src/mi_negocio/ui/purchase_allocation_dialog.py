"""Distribuir cargos ya registrados; nunca crea costos nuevos."""
from dataclasses import replace
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView
from ..purchase_allocation import ALLOCATION_FIELDS,allocation_summary
from ..purchases import categories_for
from ..sales import money
from .sales_widgets import AmountEdit,cents_text,note
from .style import STYLE,format_cop
from .form_validation import check,amount_issue


class PurchaseAllocationDialog(QDialog):
    def __init__(self,draft,names,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Distribuir costos registrados · Nimbo')
        self.setWindowModality(Qt.WindowModal);self.setStyleSheet(STYLE);self.resize(1050,460)
        self.categories=categories_for(draft);self.keys={key:ALLOCATION_FIELDS.get(key,key) for key in self.categories}
        self.draft=draft;self.result_lines=None;self.fields=[]
        root=QVBoxLayout(self);root.addWidget(note('Distribuir costos entre productos','cardTitle'))
        root.addWidget(note('Estos importes son parte de los cargos ya registrados en el pedido. No se suman de nuevo. Indica el total asignado a todas las unidades de cada fila.'))
        self.registered=allocation_summary(draft)['registered']
        root.addWidget(note('Registrado · '+' · '.join(self.categories[k]+': '+format_cop(v) for k,v in self.registered.items())))
        table=QTableWidget(len(draft.lines),1+len(self.categories));self.table=table
        table.setHorizontalHeaderLabels(['Producto / cantidad',*self.categories.values()])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().hide();root.addWidget(table,1)
        for row,line in enumerate(draft.lines):
            item=QTableWidgetItem(names[row]+' · '+str(line.quantity)+' unidades')
            item.setFlags(item.flags() & ~Qt.ItemIsEditable);item.setToolTip(item.text());table.setItem(row,0,item)
            fields={}
            for col,field in enumerate(self.keys.values(),1):
                edit=AmountEdit();edit.setText(cents_text(getattr(line,field,0) if field in ALLOCATION_FIELDS.values() else line.extra_allocations.get(field,0)));table.setCellWidget(row,col,edit);fields[field]=edit
            self.fields.append(fields);table.setRowHeight(row,56)
        self.error=note('','error');root.addWidget(self.error)
        buttons=QHBoxLayout();cancel=QPushButton('Cancelar');save=QPushButton('Aplicar distribución');save.setObjectName('primary')
        buttons.addStretch();buttons.addWidget(cancel);buttons.addWidget(save);root.addLayout(buttons)
        cancel.clicked.connect(self.reject);save.clicked.connect(self.apply)

    def apply(self):
        issues=[amount_issue(edit,'Importe asignado') for row in self.fields for edit in row.values()]
        if not check(self,issues,self.error):return
        lines=tuple(replace(line,**{field:money(edit.text()) for field,edit in row.items() if field in ALLOCATION_FIELDS.values()},extra_allocations={field:money(edit.text()) for field,edit in row.items() if field not in ALLOCATION_FIELDS.values()}) for line,row in zip(self.draft.lines,self.fields))
        remaining=allocation_summary(replace(self.draft,lines=lines))['remaining']
        issues=[]
        for key,value in remaining.items():
            if value<0:
                field=self.keys[key]
                edit=next(row[field] for row in self.fields if money(row[field].text())>0)
                issues.append((edit,self.categories[key]+': la distribución supera el costo registrado. Corrige el importe o registra primero el cargo en el pedido.'))
        if not check(self,issues,self.error):return
        self.result_lines=lines;self.accept()
