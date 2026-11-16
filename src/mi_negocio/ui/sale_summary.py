"""Resumen visual de cobro, gastos conocidos y neto; no calcula utilidad."""
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QFrame,QPushButton
from .sales_widgets import note
from .style import format_cop
from ..sales import informative_withholding


class SaleSummary(QWidget):
    def __init__(self,parent=None,vertical=False):
        super().__init__(parent)
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(3)
        cards=QVBoxLayout() if vertical else QHBoxLayout();cards.setSpacing(8);root.addLayout(cards)
        self.values=[];self.details=[]
        for title,name in [('Total al cliente','chargeSummary'),('Comisión y envío','expenseSummary'),('Te queda después','netSummary')]:
            frame=QFrame();frame.setObjectName('' if vertical else name);body=QVBoxLayout(frame);body.setContentsMargins(10,3,10,3);body.setSpacing(2)
            heading=QVBoxLayout() if vertical and not self.values else QHBoxLayout();heading.addWidget(note(title,'fieldHeading'));value=note('—','summaryAmount');heading.addWidget(value);body.addLayout(heading)
            detail=note('Sin calcular');body.addWidget(detail);cards.addWidget(frame,1);self.values.append(value);self.details.append(detail)
            if vertical:detail.hide()
        if vertical:
            self.values[0].setStyleSheet('font-size: 27px; font-weight: 700; color: #162e50;')
            self.values[2].setStyleSheet('font-size: 18px; font-weight: 700; color: #137844;')
        if vertical:
            self.expand=QPushButton('Ver desglose');self.expand.setObjectName('quietAction');self.expand.setCheckable(True);root.addWidget(self.expand)
            self.expand.toggled.connect(lambda visible:[detail.setVisible(visible) for detail in self.details])
        self.vat_information=note('');root.addWidget(self.vat_information);self.vat_information.hide()
        self.information=note('Agrega productos y elige una forma de pago.');root.addWidget(self.information)

    def setText(self,text):
        for value,detail in zip(self.values,self.details):value.setText('—');detail.setText('Sin calcular')
        self.vat_information.hide()
        self.information.setText(text)

    def update_amounts(self,subtotal,total,commission,shipping,received,withholding,*,vat_cents=0,base_cents=0,vat_enabled=False,withholding_deducted=True):
        self.vat_information.setVisible(vat_enabled)
        self.vat_information.setText(f'Base: {format_cop(base_cents)} · IVA: {format_cop(vat_cents)}')
        retained=informative_withholding(total) if withholding and withholding_deducted else 0
        for label,value in zip(self.values,(total,commission+shipping,total-commission-shipping-retained)):label.setText(format_cop(value))
        self.details[0].setText(f'Productos: {format_cop(subtotal)}\nEnvío cobrado: {format_cop(total-subtotal)}')
        self.details[1].setText(f'Comisión {"real" if received else "estimada"}: {format_cop(commission)}\nCosto del envío: {format_cop(shipping)}')
        self.details[2].setText(f'Depósito {"recibido" if received else "estimado"}: {format_cop(total-commission-retained)}\nNeto tras comisión y envío; no es utilidad.')
        if withholding and withholding_deducted:
            self.information.setText(f'Retención de renta (2,5 %): {format_cop(retained)} · Se descuenta del depósito y se registra en Retenciones de renta al confirmar el cobro.')
            return
        self.information.setText(f'Retención informativa (2,5 %): {format_cop(informative_withholding(total))} · No se descuenta del neto.' if withholding else 'No incluye el costo de la mercancía ni otros gastos del negocio.')
