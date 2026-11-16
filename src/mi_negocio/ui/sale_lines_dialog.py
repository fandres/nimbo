from .numeric_spinbox import NumericSpinBox as QSpinBox
"""Corrección provisional de líneas; solo el detalle guarda en la base."""
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QTableWidget,QPushButton,QComboBox,QHeaderView
from ..sales import SaleLineInput,money
from .sales_widgets import amount,note
from .form_validation import check,choice,amount_issue
from .style import STYLE


class SaleLinesDialog(QDialog):
    def __init__(self,connection,lines,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Corregir productos de la venta');self.resize(900,480);self.setStyleSheet(STYLE)
        self.rows=[];self.result_lines=None
        root=QVBoxLayout(self)
        root.addWidget(note('Productos, cantidades y precios','cardTitle'))
        root.addWidget(note('Los cambios se aplicarán al pulsar Guardar cambios en el detalle. Se comprobará el stock disponible.'))
        self.catalog=[dict(r) for r in connection.execute('SELECT id,code,name,active FROM products ORDER BY name')]
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Producto','Cantidad','Precio · COP',''])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.table.setColumnWidth(1,110);self.table.setColumnWidth(2,180);self.table.setColumnWidth(3,85)
        root.addWidget(self.table,1)
        for line in lines:self.add_line(line)
        add=QPushButton('+ Agregar producto');add.clicked.connect(lambda:self.add_line());root.addWidget(add)
        self.error=note('','error');root.addWidget(self.error)
        footer=QHBoxLayout();cancel=QPushButton('Cancelar');apply=QPushButton('Aplicar al detalle');apply.setObjectName('primary')
        footer.addWidget(cancel);footer.addWidget(apply);root.addLayout(footer)
        cancel.clicked.connect(self.reject);apply.clicked.connect(self.apply)

    def add_line(self,line=None):
        row=self.table.rowCount();self.table.insertRow(row)
        product=QComboBox();product.addItem('Selecciona un producto',None)
        for p in self.catalog:
            if p['active'] or (line and p['id']==line.product_id):product.addItem(p['code']+' · '+p['name'],p['id'])
        qty=QSpinBox();qty.setRange(1,999999999);price=amount(line.unit_price_cents if line else 0)
        if line:product.setCurrentIndex(product.findData(line.product_id));qty.setValue(line.quantity)
        remove=QPushButton('Quitar');remove.setObjectName('removeAction')
        controls=(product,qty,price,remove);self.rows.append(controls)
        for col,w in enumerate(controls):self.table.setCellWidget(row,col,w)
        self.table.setRowHeight(row,54)
        remove.clicked.connect(lambda:self.remove_line(controls))

    def remove_line(self,controls):
        row=self.rows.index(controls);self.rows.pop(row);self.table.removeRow(row)

    def apply(self):
        issues=[]
        for product,qty,price,_ in self.rows:
            issues.extend([choice(product,'un producto'),amount_issue(price,'Precio')])
        if not self.rows:issues.append((self.table,'Agrega al menos un producto o servicio.'))
        if not check(self,issues,self.error):return
        self.result_lines=tuple(SaleLineInput(p.currentData(),q.value(),money(v.text())) for p,q,v,_ in self.rows)
        self.accept()
