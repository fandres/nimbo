"""Confirmación breve de cobros y selección de su forma de pago."""
from PySide6.QtCore import QDate,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QHBoxLayout,QPushButton,QComboBox,QCheckBox
from ..sales import ReceiptInput,SaleLineInput,calculate_totals,money
from ..commissions import effective_fee
from ..withholding import deducted
from ..catalog import ValidationError
from ..storage import StorageError
from .sales_widgets import note,date_edit,account_combo,amount,cents_text,error_text
from .form_validation import check,choice,amount_issue
from .style import STYLE,format_cop


class PaymentMethodCombo(QComboBox):
    def __init__(self,settings,sale,parent=None):
        super().__init__(parent);self.original_id=sale['method_id'];self.methods={m.id:m for m in settings.list_methods()}
        # The saved snapshot is retained until the user explicitly chooses another method.
        self.addItem(sale['method_name'],self.original_id)
        for method in self.methods.values():
            if method.id!=self.original_id:self.addItem(method.name,method.id)
        self.setAccessibleName('Forma de pago')
    def changed_method(self):
        return self.methods.get(self.currentData()) if self.currentData()!=self.original_id else None


def estimated_commission(method,total):
    rate,fixed=effective_fee(method,total)
    return calculate_totals((SaleLineInput(0,1,total),),0,0,rate,fixed).commission_cents


class ReceiptDialog(QDialog):
    saved=Signal(int)
    def __init__(self,sale_id,settings,sales,parent=None):
        super().__init__(parent);self.sales=sales;self.sale=sales.get(sale_id)
        if not sales.permissions()['edit']:raise StorageError('Esta acción está deshabilitada en Configuración → Ventas.')
        if self.sale['cancelled_at'] or self.sale['received']:raise StorageError('La venta ya está cobrada o anulada. Actualiza el listado.')
        self.setWindowTitle(f'Confirmar cobro · Venta #{sale_id} — Nimbo');self.setModal(True);self.setStyleSheet(STYLE);self.resize(520,390)
        root=QVBoxLayout(self);root.setContentsMargins(20,18,20,18)
        root.addWidget(note('Confirmar cobro','heading'))
        root.addWidget(note(f"Venta #{sale_id} · {self.sale['customer_name']}\nTotal al cliente: {format_cop(self.sale['total_cents'])}"))
        self.receipt_date=date_edit();self.receipt_date.setMinimumDate(QDate.fromString(self.sale['sold_on'],'yyyy-MM-dd'))
        self.account=account_combo(settings,self.sale['destination_account_id'])
        self.method=PaymentMethodCombo(settings,self.sale);self.method.setEnabled(sales.permissions()['edit'])
        form=QFormLayout();form.addRow('Día del pago',self.receipt_date);form.addRow('Cuenta que recibió',self.account);form.addRow('Forma de pago',self.method);root.addLayout(form)
        self.adjust=QCheckBox('Ajustar comisión');root.addWidget(self.adjust)
        self.commission=amount(self.sale['commission_cents']);self.commission.setAccessibleName('Comisión · COP');self.commission.hide();root.addWidget(self.commission)
        self.summary=note('','saleSummary');root.addWidget(self.summary)
        self.error=note('','error');self.error.hide();root.addWidget(self.error)
        footer=QHBoxLayout();cancel=QPushButton('Cancelar');cancel.clicked.connect(self.reject);footer.addWidget(cancel)
        self.confirm=QPushButton('Confirmar cobro');self.confirm.setObjectName('primary');self.confirm.clicked.connect(self.persist);footer.addWidget(self.confirm);root.addLayout(footer)
        self.adjust.toggled.connect(self.update_fee);self.method.currentIndexChanged.connect(self.update_fee);self.commission.textChanged.connect(self.update_summary)
        self.update_summary()
    def update_fee(self,*_):
        self.commission.setVisible(self.adjust.isChecked())
        try:
            method=self.method.changed_method()
            fee=estimated_commission(method,self.sale['total_cents']) if method else self.sale['commission_cents']
            self.commission.setText(cents_text(fee));self.error.hide();self.confirm.setEnabled(True);self.update_summary()
        except ValidationError as exc:
            self.error.setText(error_text(exc));self.error.show();self.confirm.setEnabled(False)
    def update_summary(self):
        try:
            fee=money(self.commission.text());retained=deducted(self.sale);net=self.sale['total_cents']-fee-retained
            self.summary.setText(f'Comisión: {format_cop(fee)}\nRetención: {format_cop(retained)}\nIngreso a la cuenta: {format_cop(net)}')
        except ValidationError:self.summary.setText('Revisa el importe de la comisión.')
    def persist(self):
        if not check(self,[choice(self.account,'la cuenta del cobro'),amount_issue(self.commission,'Comisión')],self.error):return
        self.confirm.setEnabled(False)
        try:
            result=self.sales.confirm_receipt(self.sale['id'],ReceiptInput(self.receipt_date.date().toPython(),self.account.currentData(),money(self.commission.text())),payment_method=self.method.changed_method(),expected_sale=self.sale)
            self.saved.emit(result['id']);self.accept()
        except (StorageError,ValidationError) as exc:self.error.setText(error_text(exc));self.error.show()
        finally:self.confirm.setEnabled(True)
