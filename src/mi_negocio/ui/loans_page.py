"""Préstamos: saldo inicial, pagos desglosados e historial."""
from uuid import uuid4
from PySide6.QtCore import Signal,QDate,Qt
from PySide6.QtWidgets import QWidget,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QInputDialog
from .form_validation import required_reason, check, required, choice, amount_issue
from ..sales import money
from ..catalog import ValidationError
from ..storage import StorageError
from .sales_widgets import note,date_edit,AmountEdit,error_text,cents_text
from .expense_dialog import history_dialog
from .style import format_cop


class LoanDialog(QDialog):
    def __init__(self,repository,parent=None,loan=None):
        super().__init__(parent);self.repository=repository;self.loan=loan;self.request_id=uuid4().hex
        self.setWindowTitle('Préstamo · Nimbo');self.resize(560,380)
        box=QVBoxLayout(self);box.addWidget(note('Saldo inicial del préstamo','cardTitle'))
        box.addWidget(note('Registra el capital que aún debes en esta fecha. No incluye intereses futuros ni registra un ingreso en una cuenta.'))
        form=QFormLayout();self.name=QLineEdit();self.opened=date_edit();self.principal=AmountEdit('0,00')
        form.addRow('Entidad o nombre *',self.name);form.addRow('Fecha del saldo inicial',self.opened);form.addRow('Capital pendiente · COP *',self.principal);box.addLayout(form)
        if loan:self.name.setText(loan['name']);self.opened.setDate(QDate.fromString(loan['opened_on'],'yyyy-MM-dd'));self.principal.setText(cents_text(loan['principal_cents']))
        self.error=note('','error');box.addWidget(self.error)
        save=QPushButton('Guardar préstamo');save.setObjectName('primary');save.clicked.connect(self.persist);box.addWidget(save)
        close=QPushButton('Cancelar');close.clicked.connect(self.reject);box.addWidget(close)
    def persist(self):
        if not check(self,[required(self.name,'la entidad o nombre'),amount_issue(self.principal,'Capital pendiente',True)],self.error):return
        try:
            self.repository.save_loan(self.name.text(),self.opened.date().toPython(),money(self.principal.text()),request_id=self.request_id,loan_id=self.loan['id'] if self.loan else None,expected_revision=self.loan['revision'] if self.loan else None);self.accept()
        except (StorageError,ValidationError) as e:self.error.setText(error_text(e))


class LoanPaymentDialog(QDialog):
    def __init__(self,repository,settings,loan,parent=None):
        super().__init__(parent);self.repository=repository;self.loan=loan;self.request_id=uuid4().hex
        self.setWindowTitle('Registrar pago de préstamo · Nimbo');self.resize(600,460)
        root=QVBoxLayout(self);root.addWidget(note(loan['name'],'cardTitle'));root.addWidget(note('Capital pendiente: '+format_cop(loan['balance_cents'])))
        form=QFormLayout();self.paid_on=date_edit();self.account=QComboBox();self.account.addItem('Selecciona una cuenta',None)
        for account in settings.list_accounts():self.account.addItem(account.name,account.id)
        self.capital=AmountEdit('0,00');self.interest=AmountEdit('0,00');self.note=QLineEdit()
        for title,w in [('Fecha de pago',self.paid_on),('Cuenta *',self.account),('Abono a capital · COP',self.capital),('Intereses · COP',self.interest),('Nota · opcional',self.note)]:form.addRow(title,w)
        root.addLayout(form);self.total=note('','sectionValue');root.addWidget(self.total)
        root.addWidget(note('Registra solo pagos realizados. El capital reduce la deuda; los intereses aparecen automáticamente en Gastos. No vuelvas a registrar esta cuota como gasto.'))
        self.error=note('','error');root.addWidget(self.error)
        save=QPushButton('Guardar pago');save.setObjectName('primary');save.clicked.connect(self.persist);root.addWidget(save)
        close=QPushButton('Cancelar');close.clicked.connect(self.reject);root.addWidget(close)
        self.capital.textChanged.connect(self.update_total);self.interest.textChanged.connect(self.update_total);self.update_total()
    def update_total(self):
        try:self.total.setText('Total pagado: '+format_cop(money(self.capital.text())+money(self.interest.text())))
        except ValidationError:self.total.setText('Total pagado: —')
    def persist(self):
        issues=[choice(self.account,'una cuenta'),amount_issue(self.capital,'Abono a capital'),amount_issue(self.interest,'Intereses')]
        if not any(issues[1:]):
            if money(self.capital.text())+money(self.interest.text())<=0:issues.append((self.capital,'Escribe un abono a capital o intereses mayor que cero.'))
            if money(self.capital.text())>self.loan['balance_cents']:issues.append((self.capital,'El abono supera el capital pendiente.'))
        if self.paid_on.date().toString('yyyy-MM-dd')<self.loan['opened_on']:issues.append((self.paid_on,'El pago no puede ser anterior al saldo inicial.'))
        if not check(self,issues,self.error):return
        try:
            self.repository.pay(self.loan['id'],self.paid_on.date().toPython(),self.account.currentData(),money(self.capital.text()),money(self.interest.text()),request_id=self.request_id,note=self.note.text());self.accept()
        except (StorageError,ValidationError) as e:self.error.setText(error_text(e))


def table(headers):
    result=QTableWidget(0,len(headers));result.setHorizontalHeaderLabels(headers);result.verticalHeader().hide();result.verticalHeader().setDefaultSectionSize(42)
    result.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);result.setSelectionBehavior(QTableWidget.SelectRows);result.setSelectionMode(QTableWidget.SingleSelection);result.setEditTriggers(QTableWidget.NoEditTriggers)
    return result


class LoansPage(QWidget):
    changed=Signal()
    def __init__(self,repository,settings,parent=None):
        super().__init__(parent);self.repository=repository;self.settings=settings;self.rows=[];self.payment_rows=[]
        root=QVBoxLayout(self);root.setContentsMargins(0,10,0,0)
        header=QHBoxLayout();self.balance=note('','sectionValue');header.addWidget(self.balance,1);new=QPushButton('+ Nuevo préstamo');new.setObjectName('primary');header.addWidget(new);root.addLayout(header)
        root.addWidget(note('Saldos actuales de capital · Todos los préstamos. Los intereses se muestran en Gastos; el capital no se suma a los gastos.'))
        self.table=table(['Entidad / préstamo','Saldo inicial · COP','Capital pendiente · COP','Estado']);root.addWidget(self.table,1)
        actions=QHBoxLayout();pay=QPushButton('Registrar pago');pay.setObjectName('primary');edit=QPushButton('Corregir saldo inicial');history=QPushButton('Historial');actions.addWidget(pay);actions.addWidget(edit);actions.addWidget(history);root.addLayout(actions)
        root.addWidget(note('Pagos del préstamo seleccionado','cardTitle'));self.payments=table(['Fecha','Cuenta','Capital · COP','Intereses · COP','Total · COP','Estado']);root.addWidget(self.payments,1)
        cancel=QPushButton('Anular pago seleccionado');cancel.setObjectName('removeAction');root.addWidget(cancel)
        self.error=note('','error');root.addWidget(self.error)
        new.clicked.connect(self.new_loan);pay.clicked.connect(self.new_payment);edit.clicked.connect(self.edit_loan);history.clicked.connect(self.show_history);cancel.clicked.connect(self.cancel_payment);self.table.itemSelectionChanged.connect(self.refresh_payments);self.refresh()

    def selected(self):
        i=self.table.currentRow();return self.rows[i] if 0<=i<len(self.rows) else None

    def refresh(self):
        try:
            previous=self.selected();key=previous['id'] if previous else None
            self.rows=self.repository.list_loans();self.table.blockSignals(True);self.table.setRowCount(len(self.rows))
            for i,r in enumerate(self.rows):
                for j,value in enumerate([r['name'],format_cop(r['principal_cents']),format_cop(r['balance_cents']),'Saldado' if r['balance_cents']==0 else 'Vigente']):self.table.setItem(i,j,QTableWidgetItem(value))
            self.table.blockSignals(False);self.balance.setText('Capital pendiente: '+format_cop(sum(r['balance_cents'] for r in self.rows)))
            self.table.selectRow(next((i for i,r in enumerate(self.rows) if r['id']==key),0));self.refresh_payments();self.error.clear()
        except StorageError as e:self.error.setText(str(e))

    def select_loan(self,key):
        self.refresh()
        for i,r in enumerate(self.rows):
            if r['id']==key:self.table.selectRow(i);break

    def refresh_payments(self):
        row=self.selected()
        try:
            self.payment_rows=self.repository.payments(row['id']) if row else [];self.payments.setRowCount(len(self.payment_rows))
            for i,p in enumerate(self.payment_rows):
                for j,value in enumerate([p['paid_on'],p['account'],format_cop(p['capital_cents']),format_cop(p['interest_cents']),format_cop(p['capital_cents']+p['interest_cents']),'Anulado' if p['cancelled_at'] else 'Pagado']):
                    item=QTableWidgetItem(value);item.setToolTip(p['cancellation_reason'] or p['note']);self.payments.setItem(i,j,item)
        except StorageError as e:self.error.setText(str(e))

    def new_loan(self):
        if LoanDialog(self.repository,self).exec():self.refresh();self.changed.emit()
    def edit_loan(self):
        row=self.selected()
        if row and LoanDialog(self.repository,self,row).exec():self.refresh();self.changed.emit()
    def new_payment(self):
        row=self.selected()
        if row and LoanPaymentDialog(self.repository,self.settings,row,self).exec():self.refresh();self.changed.emit()
    def cancel_payment(self):
        index=self.payments.currentRow()
        if not 0<=index<len(self.payment_rows):return
        reason,ok=required_reason(self,'Anular pago','Motivo (se restituirá el capital al saldo pendiente):')
        if not ok:return
        try:self.repository.cancel_payment(self.payment_rows[index]['id'],reason);self.refresh();self.changed.emit()
        except StorageError as e:self.error.setText(str(e))
    def show_history(self):
        import json
        row=self.selected()
        if not row:return
        try:
            events=self.repository.history(row['id'])
            history_dialog('Historial del préstamo','\n\n'.join(e['changed_at']+' · '+e['description']+'\n'+json.dumps(json.loads(e['snapshot']),ensure_ascii=False,indent=2) for e in events),self)
        except StorageError as e:self.error.setText(str(e))
