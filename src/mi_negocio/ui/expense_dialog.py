"""Registro horizontal de gasto, pago y datos opcionales."""
from .attachments_dialog import attachment_button
from datetime import date
from uuid import uuid4
from PySide6.QtCore import Signal,QDate
from PySide6.QtWidgets import QDialog,QWidget,QFrame,QScrollArea,QVBoxLayout,QHBoxLayout,QGridLayout,QLineEdit,QComboBox,QPushButton,QCheckBox,QButtonGroup,QInputDialog,QMessageBox
from .form_validation import required_reason, check, required, choice, amount_issue
from ..expenses import ExpenseDraft
from ..sales import money
from ..storage import StorageError
from ..catalog import ValidationError
from .sales_widgets import note,AmountEdit,cents_text,date_edit,error_text
from .style import format_cop
from .expense_categories import edit_categories
from .expense_concept import ExpenseConceptEdit


def field(layout,row,column,title,widget,span=1):
    box=QVBoxLayout();box.setSpacing(4);box.addWidget(note(title,'fieldHeading'));box.addWidget(widget);layout.addLayout(box,row,column,1,span)


def history_dialog(title,text,parent):
    from PySide6.QtWidgets import QPlainTextEdit
    dialog=QDialog(parent);dialog.setWindowTitle(title);dialog.resize(780,520)
    box=QVBoxLayout(dialog);content=QPlainTextEdit();content.setReadOnly(True);content.setPlainText(text);box.addWidget(content)
    close=QPushButton('Cerrar');close.clicked.connect(dialog.accept);box.addWidget(close);dialog.exec()


class ExpenseDialog(QDialog):
    saved=Signal()
    def __init__(self,repository,settings,parent=None,expense_id=None,mark_paid=False):
        super().__init__(parent);self.repository=repository;self.settings=settings;self.expense_id=expense_id;self.request_id=uuid4().hex
        self.original=repository.get(expense_id) if expense_id else None
        self.setWindowTitle(('Editar gasto' if expense_id else 'Nuevo gasto')+' · Nimbo')
        screen=self.screen().availableGeometry();self.resize(min(1120,screen.width()-32),min(780,screen.height()-48))
        root=QVBoxLayout(self);root.setContentsMargins(24,18,24,18);root.setSpacing(14)
        title_row=QHBoxLayout();title_row.addWidget(note('Editar gasto' if expense_id else 'Nuevo gasto','heading'),1)
        if expense_id is not None:title_row.addWidget(attachment_button(repository.connection,'expense',expense_id,self))
        root.addLayout(title_row)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame);root.addWidget(scroll,1)
        body=QWidget();scroll.setWidget(body);columns=QHBoxLayout(body);columns.setContentsMargins(0,0,0,0);columns.setSpacing(18)
        form=QFrame();form.setObjectName('saleSection');left=QVBoxLayout(form);left.setContentsMargins(18,18,18,18);left.setSpacing(10);columns.addWidget(form,2)
        grid=QGridLayout();grid.setHorizontalSpacing(12);grid.setVerticalSpacing(12);grid.setColumnStretch(0,1);grid.setColumnStretch(1,1)
        self.concept=ExpenseConceptEdit(repository);self.concept.setPlaceholderText('Ej. Publicidad, hosting o insumos del taller')
        self.amount=AmountEdit('0,00');self.spent_on=date_edit()
        field(grid,0,0,'Concepto *',self.concept,2);field(grid,1,0,'Valor · COP *',self.amount);field(grid,1,1,'Fecha del gasto',self.spent_on)
        left.addLayout(grid);left.addWidget(note('Categoría *','fieldHeading'))
        self.category=QComboBox();left.addWidget(self.category)
        self.quick=QGridLayout();left.addLayout(self.quick);self.category_buttons=[];self.category_group=QButtonGroup(self);self.category_group.setExclusive(True)
        self.category.currentIndexChanged.connect(self._category_selected)
        edit=QPushButton('+ Nueva / editar categorías');edit.setObjectName('quietAction');edit.clicked.connect(self._categories);left.addWidget(edit)
        line=QFrame();line.setFrameShape(QFrame.HLine);left.addWidget(line)
        left.addWidget(note('¿Ya lo pagaste?','fieldHeading'))
        choices=QHBoxLayout();self.paid=QPushButton('Pagado');self.pending=QPushButton('Pendiente por pagar');self.payment_group=QButtonGroup(self)
        for button in (self.paid,self.pending):button.setCheckable(True);button.setObjectName('paymentChoice');self.payment_group.addButton(button);choices.addWidget(button)
        self.paid.setChecked(True);left.addLayout(choices)
        payment=QGridLayout();payment.setColumnStretch(0,1);payment.setColumnStretch(1,1);self.account=QComboBox();self.account.addItem('Selecciona una cuenta',None)
        previous=self.original['account_id'] if self.original else None
        for a in settings.list_accounts(True, include_cards=True):
            if a.id==previous or (a.enabled and (not settings.connection.execute('SELECT 1 FROM credit_cards WHERE account_id=?',(a.id,)).fetchone() or settings.connection.execute('SELECT enabled FROM credit_card_settings WHERE id=1').fetchone()[0])):self.account.addItem(a.name+(' · Deshabilitada' if not a.enabled else ''),a.id)
        self.paid_on=date_edit();field(payment,0,0,'Cuenta desde la que pagaste *',self.account);field(payment,0,1,'Fecha de pago',self.paid_on);left.addLayout(payment)
        due=QHBoxLayout();self.has_due=QCheckBox('Fecha estimada de pago · opcional');self.due_on=date_edit();self.due_on.setMaximumDate(QDate(9999,12,31));due.addWidget(self.has_due);due.addWidget(self.due_on);left.addLayout(due)
        self.more=QPushButton('+ Agregar nota o referencia de comprobante');self.more.setCheckable(True);self.more.setObjectName('quietAction');left.addWidget(self.more)
        self.optional=QWidget();optional=QVBoxLayout(self.optional);optional.setContentsMargins(0,0,0,0)
        self.note=QLineEdit();self.note.setPlaceholderText('Nota opcional');self.voucher=QLineEdit();self.voucher.setPlaceholderText('Número o referencia del comprobante · opcional');optional.addWidget(self.note);optional.addWidget(self.voucher);left.addWidget(self.optional);self.optional.hide();self.more.toggled.connect(self.optional.setVisible)
        left.addStretch()
        aside=QFrame();aside.setObjectName('saleSection');right=QVBoxLayout(aside);right.setContentsMargins(18,18,18,18);right.setSpacing(12);columns.addWidget(aside,1)
        right.addWidget(note('SE REGISTRARÁ'));self.total=note('—','heading');right.addWidget(self.total)
        self.explanation=note('');right.addWidget(self.explanation)
        self.save_button=QPushButton('Guardar cambios' if expense_id else 'Guardar gasto');self.save_button.setObjectName('primary');right.addWidget(self.save_button)
        close=QPushButton('Cancelar');close.clicked.connect(self.reject);right.addWidget(close)
        if expense_id:
            history=QPushButton('Ver historial');history.clicked.connect(self.show_history);right.addWidget(history)
            self.cancel_button=QPushButton('Anular gasto');self.cancel_button.setObjectName('removeAction');self.cancel_button.clicked.connect(self.cancel_expense);right.addWidget(self.cancel_button)
        right.addWidget(note('No dupliques: las comisiones y envíos de ventas aparecen automáticamente. La mercancía se registra en Compras. Las cuotas se registran en Préstamos, separando capital e intereses.'))
        self.error=note('','error');right.addWidget(self.error);right.addStretch()
        self.concept.concept_selected.connect(self._select_concept_category)
        self.concept.lookup_failed.connect(self.error.setText)
        self._load_categories(self.original['category_id'] if self.original else None)
        if self.original:
            r=self.original;self.concept.setText(r['concept']);self.amount.setText(cents_text(r['amount_cents']));self.spent_on.setDate(QDate.fromString(r['spent_on'],'yyyy-MM-dd'))
            (self.paid if r['paid_on'] else self.pending).setChecked(True)
            if r['paid_on']:self.paid_on.setDate(QDate.fromString(r['paid_on'],'yyyy-MM-dd'))
            self.account.setCurrentIndex(max(0,self.account.findData(r['account_id'])))
            if r['due_on']:self.has_due.setChecked(True);self.due_on.setDate(QDate.fromString(r['due_on'],'yyyy-MM-dd'))
            self.note.setText(r['note']);self.voucher.setText(r['voucher']);self.more.setChecked(bool(r['note'] or r['voucher']))
            if r['cancelled_at']:
                form.setEnabled(False);self.save_button.setEnabled(False);self.cancel_button.setEnabled(False);self.error.setText('Gasto anulado: '+r['cancellation_reason'])
        if mark_paid:self.paid.setChecked(True);self.paid_on.setDate(QDate.currentDate())
        self.paid.toggled.connect(self._payment_changed);self.has_due.toggled.connect(self._payment_changed)
        self.amount.textChanged.connect(self._amount_changed);self.save_button.clicked.connect(self.persist)
        for button in self.findChildren(QPushButton):button.setAutoDefault(False)
        self._payment_changed();self._amount_changed();self.concept.setFocus()

    def _select_concept_category(self,key):
        # Refresh names and availability after editing categories in another dialog.
        try:
            enabled={row['id'] for row in self.repository.categories()}
            self._load_categories(key if key in enabled else None)
            if key not in enabled:self.error.setText('La categoría de este concepto fue deshabilitada. Elige otra.')
        except StorageError as error:self.error.setText(str(error))

    def _load_categories(self,selected=None):
        self.category.clear();self.category.addItem('Selecciona una categoría',None)
        for button in self.category_buttons:self.category_group.removeButton(button);button.hide();button.deleteLater()
        self.category_buttons=[]
        while self.quick.count():self.quick.takeAt(0)
        available=[]
        for row in self.repository.categories(True):
            if row['enabled'] or row['id']==selected:self.category.addItem(row['name'],row['id'])
            if row['enabled']:available.append(row)
        for i,row in enumerate(available[:6]):
            button=QPushButton(row['name']);button.setCheckable(True);button.setObjectName('paymentChoice');button.setAutoDefault(False)
            button.clicked.connect(lambda checked=False,key=row['id']:self.category.setCurrentIndex(self.category.findData(key)))
            self.category_group.addButton(button,row['id']);self.quick.addWidget(button,i//3,i%3);self.category_buttons.append(button)
        self.category.setCurrentIndex(max(0,self.category.findData(selected)));self._category_selected()

    def _category_selected(self,*args):
        self.category_group.setExclusive(False)
        for b in self.category_buttons:b.setChecked(self.category_group.id(b)==self.category.currentData())
        self.category_group.setExclusive(True)

    def _categories(self):
        key=self.category.currentData();edit_categories(self.repository,self);self._load_categories(key)

    def _payment_changed(self,*args):
        paid=self.paid.isChecked();self.account.setEnabled(paid);self.paid_on.setEnabled(paid);self.has_due.setVisible(not paid);self.due_on.setVisible(not paid);self.due_on.setEnabled(not paid and self.has_due.isChecked())
        self.explanation.setText('Se registrará el pago en la cuenta y fecha elegidas.' if paid else 'El gasto contará en el período. No registrará salida de dinero hasta que lo marques pagado.')

    def _amount_changed(self,*args):
        try:self.total.setText(format_cop(money(self.amount.text())))
        except ValidationError:self.total.setText('—')

    def persist(self):
        issues=[required(self.concept,'el concepto'), amount_issue(self.amount,'Valor del gasto',True), choice(self.category,'una categoría')]
        if self.paid.isChecked():
            issues.append(choice(self.account,'la cuenta desde la que pagaste'))
            if self.paid_on.date()<self.spent_on.date():issues.append((self.paid_on,'La fecha de pago no puede ser anterior al gasto.'))
        elif self.has_due.isChecked() and self.due_on.date()<self.spent_on.date():
            issues.append((self.due_on,'La fecha estimada no puede ser anterior al gasto.'))
        if not check(self,issues,self.error):return
        try:
            paid=self.paid.isChecked()
            draft=ExpenseDraft(self.concept.text(),money(self.amount.text()),self.spent_on.date().toPython(),self.category.currentData(),
                self.paid_on.date().toPython() if paid else None,self.account.currentData() if paid else None,
                self.due_on.date().toPython() if self.has_due.isChecked() and not paid else None,self.note.text(),self.voucher.text())
            self.repository.save(draft,request_id=self.request_id,expense_id=self.expense_id,expected_revision=self.original['revision'] if self.original else None)
            self.saved.emit();self.accept()
        except (StorageError,ValidationError) as e:self.error.setText(error_text(e))

    def cancel_expense(self):
        reason,ok=required_reason(self,'Anular gasto','Motivo (se conserva el historial):')
        if not ok:return
        try:self.repository.cancel(self.expense_id,self.original['revision'],reason);self.saved.emit();self.accept()
        except StorageError as e:self.error.setText(str(e))

    def show_history(self):
        import json
        try:
            blocks=[]
            for event in self.repository.history(self.expense_id):
                r=json.loads(event['snapshot'])
                blocks.append(f"Revisión {event['revision']} · {event['changed_at']}\n{r['concept']} · {format_cop(r['amount_cents'])}\nFecha: {r['spent_on']} · Pago: {r['paid_on'] or 'Pendiente'}\nCategoría #{r['category_id']} · Cuenta: {r['account_id'] or '—'}\nNota: {r['note']} · Comprobante: {r['voucher']}\n{('Anulado: '+r['cancellation_reason']) if r['cancelled_at'] else 'Vigente'}")
            history_dialog('Historial del gasto','\n\n'.join(blocks),self)
        except StorageError as e:self.error.setText(str(e))
