"""Treasury forms with explicit dates, accounts and validation."""
from uuid import uuid4
from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QPushButton,QCheckBox
from ..money_repository import KINDS,PURCHASE_CATEGORIES
from ..settings_repository import SettingsRepository
from ..sales import money,Account
from ..storage import StorageError
from ..catalog import ValidationError
from .sales_widgets import note,amount,date_edit,error_text
from .form_validation import check,required,choice,amount_issue

class MoneyEntryDialog(QDialog):
    saved=Signal()
    def __init__(self,repository,parent=None,kind='contribution',card_account=None,purchase_id=None):
        super().__init__(parent);self.repository=repository;self.request_id=str(uuid4());self.setWindowTitle('Registrar movimiento · Nimbo');self.resize(760,640)
        root=QVBoxLayout(self);root.setContentsMargins(24,20,24,20);root.addWidget(note('Registrar movimiento','heading'))
        form=QFormLayout();self.kind=QComboBox()
        from ..credit_cards import CreditCardsRepository
        cards_enabled = CreditCardsRepository(repository.connection).enabled()
        for key,title in KINDS.items():
            if key != 'card_payment' or cards_enabled:
                self.kind.addItem(title,key)
        self.kind.setCurrentIndex(max(0,self.kind.findData(kind)));form.addRow('Tipo',self.kind)
        self.concept=QLineEdit();self.on=date_edit();self.value=amount();self.source=QComboBox();self.destination=QComboBox()
        form.addRow('Concepto *',self.concept);form.addRow('Fecha',self.on);form.addRow('Valor · COP *',self.value)
        form.addRow('Desde',self.source);form.addRow('Hacia',self.destination)
        self.purchase=QComboBox();self.purchase.addItem('Selecciona una compra',None)
        for r in repository.connection.execute('SELECT id,supplier,supplier_alias,purchased_on FROM purchases WHERE cancelled_at IS NULL ORDER BY purchased_on DESC,id DESC'):
            self.purchase.addItem(f"#{r['id']} · {r['supplier']}"+(" · "+r['supplier_alias'] if r['supplier_alias'] else "")+f" · {r['purchased_on']}",r['id'])
        if purchase_id:self.purchase.setCurrentIndex(self.purchase.findData(purchase_id))
        self.category=QComboBox()
        for key,title in PURCHASE_CATEGORIES.items():self.category.addItem(title,key)
        form.addRow('Compra *',self.purchase);form.addRow('Concepto pagado',self.category)
        self.capital=amount();self.interest=amount();self.fees=amount()
        form.addRow('Capital del pago · COP',self.capital);form.addRow('Intereses ya registrados · COP',self.interest);form.addRow('Otros cargos ya registrados · COP',self.fees)
        root.addLayout(form);self.form=form
        root.addWidget(note('Para pagar una tarjeta, registra primero los intereses reales si los hubo. El pago disminuye la deuda; no crea otro gasto.'))
        self.error=note('','error');root.addWidget(self.error)
        buttons=QHBoxLayout();cancel=QPushButton('Cancelar');self.save_button=QPushButton('Guardar movimiento');self.save_button.setObjectName('primary')
        buttons.addStretch();buttons.addWidget(cancel);buttons.addWidget(self.save_button);root.addLayout(buttons)
        cancel.clicked.connect(self.reject);self.save_button.clicked.connect(self.save);self.kind.currentIndexChanged.connect(self.update_fields)
        for field in (self.capital,self.interest,self.fees):field.textChanged.connect(self.payment_total)
        self.update_fields()
        if card_account:self.destination.setCurrentIndex(self.destination.findData(card_account))
    def update_fields(self):
        kind=self.kind.currentData();out=kind in ('transfer','withdrawal','purchase_payment','card_payment');incoming=kind in ('transfer','contribution','refund','loan_disbursement','card_payment')
        accounts=self.repository.balances()
        enabled=self.repository.connection.execute('SELECT enabled FROM credit_card_settings WHERE id=1').fetchone()[0]
        for combo,is_source,needed in ((self.source,True,out),(self.destination,False,incoming)):
            old=combo.currentData();combo.clear();combo.addItem('Selecciona una cuenta',None)
            for a in accounts:
                allow=(not a['is_card']) if is_source and kind!='purchase_payment' else (a['is_card'] if not is_source and kind=='card_payment' else (not a['is_card'] or (kind=='purchase_payment' and enabled)))
                if a['enabled'] and allow and a['kind']!='withholding':combo.addItem(a['name']+(' · Crédito' if a['is_card'] else ''),a['id'])
            combo.setCurrentIndex(max(0,combo.findData(old)));self.form.setRowVisible(combo,needed)
        for w in (self.purchase,self.category):self.form.setRowVisible(w,kind=='purchase_payment')
        for w in (self.capital,self.interest,self.fees):self.form.setRowVisible(w,kind=='card_payment')
        self.value.setReadOnly(kind=='card_payment')
        if kind=='card_payment':self.payment_total()
    def payment_total(self):
        if self.kind.currentData()!='card_payment':return
        try:
            from .sales_widgets import cents_text
            self.value.setText(cents_text(sum(money(w.text()) for w in (self.capital,self.interest,self.fees))))
        except ValidationError:pass
    def save(self):
        kind=self.kind.currentData();issues=[required(self.concept,'el concepto'),amount_issue(self.value,'Valor',True)]
        if not self.source.isHidden():issues.append(choice(self.source,'la cuenta de origen'))
        if not self.destination.isHidden():issues.append(choice(self.destination,'la cuenta de destino'))
        if kind=='purchase_payment':issues.append(choice(self.purchase,'la compra'))
        if kind=='card_payment':issues.extend(amount_issue(w,label) for w,label in ((self.capital,'Capital'),(self.interest,'Intereses'),(self.fees,'Cargos')))
        if not check(self,issues,self.error):return
        try:
            self.repository.add(kind,self.on.date().toPython(),money(self.value.text()),self.concept.text(),
                self.source.currentData() if not self.source.isHidden() else None,self.destination.currentData() if not self.destination.isHidden() else None,
                request_id=self.request_id,purchase_id=self.purchase.currentData() if kind=='purchase_payment' else None,
                purchase_category=self.category.currentData() if kind=='purchase_payment' else '',
                capital_cents=money(self.capital.text()) if kind=='card_payment' else 0,
                interest_cents=money(self.interest.text()) if kind=='card_payment' else 0,fee_cents=money(self.fees.text()) if kind=='card_payment' else 0)
            self.saved.emit();self.accept()
        except (StorageError,ValidationError) as e:self.error.setText(error_text(e))

class OpeningDialog(QDialog):
    saved=Signal()
    def __init__(self,repository,account,parent=None):
        super().__init__(parent);self.repository=repository;self.account=account;self.setWindowTitle('Saldo inicial · Nimbo');self.resize(580,320)
        root=QVBoxLayout(self);root.addWidget(note(account['name'],'heading'))
        root.addWidget(note('Indica el saldo al comienzo del día. Los movimientos anteriores no se volverán a sumar.'))
        form=QFormLayout();self.on=date_edit();self.value=amount(abs(account['opening_cents'] or 0));self.negative=QCheckBox('Saldo negativo / sobregiro')
        self.negative.setChecked((account['opening_cents'] or 0)<0);self.negative.setVisible(not account['is_card'])
        if account['opened_on']:self.on.setDate(QDate.fromString(account['opened_on'],'yyyy-MM-dd'))
        form.addRow('Fecha de inicio',self.on);form.addRow('Deuda inicial · COP' if account['is_card'] else 'Saldo inicial · COP',self.value);root.addLayout(form);root.addWidget(self.negative)
        self.error=note('','error');root.addWidget(self.error);buttons=QHBoxLayout();cancel=QPushButton('Cancelar');save=QPushButton('Guardar saldo inicial');save.setObjectName('primary');buttons.addWidget(cancel);buttons.addWidget(save);root.addLayout(buttons)
        cancel.clicked.connect(self.reject);save.clicked.connect(self.save)
    def save(self):
        if not check(self,[amount_issue(self.value,'Saldo inicial')],self.error):return
        try:
            value=money(self.value.text())*(-1 if self.account['is_card'] or self.negative.isChecked() else 1)
            self.repository.set_opening(self.account['id'],self.on.date().toPython(),value,self.account['revision'])
            self.saved.emit();self.accept()
        except (StorageError,ValidationError) as e:self.error.setText(error_text(e))

class AccountDialog(QDialog):
    saved=Signal()
    def __init__(self,connection,parent=None):
        super().__init__(parent);self.settings=SettingsRepository(connection);self.setWindowTitle('Nueva cuenta');root=QVBoxLayout(self)
        root.addWidget(note('Nueva cuenta','heading'));self.name=QLineEdit();self.kind=QComboBox();self.kind.addItem('Banco o billetera','bank');self.kind.addItem('Efectivo','cash')
        form=QFormLayout();form.addRow('Nombre *',self.name);form.addRow('Tipo',self.kind);root.addLayout(form);self.error=note('','error');root.addWidget(self.error)
        save=QPushButton('Guardar cuenta');save.setObjectName('primary');root.addWidget(save);save.clicked.connect(self.save);self.resize(500,250)
    def save(self):
        if not check(self,[required(self.name,'el nombre')],self.error):return
        try:self.settings.save_account(Account(0,self.name.text(),True,self.kind.currentData(),False));self.saved.emit();self.accept()
        except (StorageError,ValidationError) as e:self.error.setText(error_text(e))
