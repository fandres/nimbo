"""Detalle de venta con revisión visual y guardado atómico."""
from .preferences import DisplayPreferences
from .attachments_dialog import attachment_button
from PySide6.QtCore import Signal, QDate, Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QPushButton,
    QLineEdit,QScrollArea,QWidget,QCheckBox,QFrame,QGridLayout,QListWidget,QInputDialog,QMessageBox,QPlainTextEdit)
from .form_validation import check, choice, amount_issue, required
from ..sales import ReceiptInput,ShippingPaymentInput,money,SaleLineInput,calculate_totals
from decimal import Decimal
import json
from ..storage import StorageError
from ..catalog import ValidationError
from .sales_widgets import note,amount,date_edit,account_combo,error_text,shipping_method_combo,cents_text
from .sale_summary import SaleSummary
from .style import STYLE,format_cop


class SaleDetailDialog(QDialog):
    saved=Signal(int)

    def __init__(self,sale_id,settings,sales,parent=None,preferences=None):
        super().__init__(parent)
        self.preferences=preferences or DisplayPreferences()
        self.sale_id,self.sales,self.settings=sale_id,sales,settings
        self.sale=sales.get(sale_id)
        self.pending_lines=None
        self.setWindowTitle(f'Venta #{sale_id}')
        self.setModal(True);self.resize(1280,780);self.setMinimumSize(760,460);self.setStyleSheet(STYLE)
        root=QVBoxLayout(self);root.setContentsMargins(20,10,20,10);root.setSpacing(10)
        root.addWidget(note(f'Venta #{sale_id} · {QDate.fromString(self.sale["sold_on"],"yyyy-MM-dd").toString("dd/MM/yyyy")}', 'heading'))
        self.cancelled_notice=note('', 'error')
        root.addWidget(self.cancelled_notice);self.cancelled_notice.hide()
        customer=QFrame();customer.setObjectName('saleSection');customer_box=QVBoxLayout(customer)
        customer_box.addWidget(note('Cliente','cardTitle'))
        self.customer_info=note(f'{self.sale["customer_name"] or "Sin registrar"}\nCédula / NIT: {self.sale["customer_identification"] or "Sin registrar"} · Correo: {self.sale["customer_email"] or "Sin registrar"}')
        customer_box.addWidget(self.customer_info);root.addWidget(customer)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True)
        body=QWidget();body.setObjectName('saleBody');self.scroll.setWidget(body);root.addWidget(self.scroll,1)
        self.grid=QGridLayout(body);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(12)
        self.sections=[]
        def section(title):
            frame=QFrame();frame.setObjectName('saleSection');layout=QVBoxLayout(frame)
            layout.setContentsMargins(12,10,12,10);layout.setSpacing(8)
            layout.addWidget(note(title,'cardTitle'));self.sections.append(frame)
            return layout
        invoice=section('1 · Productos y factura')
        self.products=QListWidget();self.products.setWordWrap(True);self.products.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.products.setMinimumHeight(70);self.products.setMaximumHeight(110)
        for line in self.sale['lines']:
            text=f'{line["quantity"]} × {line["code"]} · {line["name"]} — {format_cop(line.get("line_total_cents",line["quantity"]*line["unit_price_cents"]))}'
            self.products.addItem(text);self.products.item(self.products.count()-1).setToolTip(text)
        invoice.addWidget(self.products)
        self.edit_products=QPushButton('Editar productos');self.edit_products.setObjectName('quietAction')
        heading=invoice.takeAt(0).widget();heading_row=QHBoxLayout();heading_row.addWidget(heading,1);heading_row.addWidget(self.edit_products)
        invoice.insertLayout(0,heading_row);self.edit_products.clicked.connect(self.edit_lines)
        self.invoice_caption=note('Factura electrónica · opcional','fieldHeading');invoice.addWidget(self.invoice_caption)
        self.invoice=QLineEdit(self.sale['invoice_ref']);self.invoice.setPlaceholderText('Ej. FE-123');invoice.addWidget(self.invoice)
        self.withholding=QCheckBox('Se aplicó retención');self.withholding.setChecked(bool(self.sale['has_withholding']))
        invoice.addWidget(self.withholding);invoice.addWidget(note('Retención · 2,5 % del total; descontada del depósito.' if self.sale['withholding_deducted'] else 'Histórica informativa · 2,5 % del total.'))
        self.email_caption=note('Correo del cliente · opcional','fieldHeading');invoice.addWidget(self.email_caption)
        self.customer_email=QLineEdit(self.sale['customer_email']);self.customer_email.setPlaceholderText('nombre@correo.com');invoice.addWidget(self.customer_email)
        extra=QHBoxLayout()
        self.customer_alias=QLineEdit(self.sale['customer_alias']);self.customer_phone=QLineEdit(self.sale['customer_phone'])
        for title,control in [('Alias o detalles · opcional',self.customer_alias),('Celular · opcional',self.customer_phone)]:
            column=QVBoxLayout();column.addWidget(note(title,'fieldHeading'));column.addWidget(control);control.setAccessibleName(title);extra.addLayout(column)
        invoice.addLayout(extra)
        self.withholding.toggled.connect(self._update_retention_requirement);self._update_retention_requirement()
        invoice.addStretch()
        receipt=section('2 · Cobro de la venta')
        receipt.addWidget(note(self.sale['method_name']+(' · '+self.sale['provider'] if self.sale['provider'] else ''),'fieldHeading'))
        self.received=QCheckBox('Ya recibí el dinero');receipt.addWidget(self.received)
        self.receipt_status=note('');receipt.addWidget(self.receipt_status)
        self.receipt_date=date_edit();self.account=account_combo(settings,self.sale['destination_account_id']);self.commission=amount(self.sale['commission_cents'])
        receipt_form=QFormLayout();receipt_form.setSpacing(8)
        receipt_form.addRow('Recibido el',self.receipt_date);receipt_form.addRow('Cuenta',self.account);receipt_form.addRow('Comisión · COP',self.commission)
        receipt.addLayout(receipt_form);receipt.addStretch()
        shipping=section('3 · Envío')
        shipping.addWidget(note(f'Transportadora: {self.sale["carrier_name"] or "Sin especificar"}\nDestino: {self.sale["destination_city"] or "Sin especificar"}'))
        shipping.addWidget(note('Guía / tracking · opcional','fieldHeading'))
        self.tracking=QLineEdit(self.sale['tracking_number']);self.tracking.setEnabled(bool(self.sale['shipping_enabled']));shipping.addWidget(self.tracking)
        self.shipping_paid=QCheckBox('Ya pagué el envío');shipping.addWidget(self.shipping_paid)
        self.shipping_date=date_edit();self.shipping_account=account_combo(settings);self.shipping_account.setItemText(0,'Cuenta (opcional)')
        from .sales_widgets import refresh_shipping_accounts
        self.shipping_method=shipping_method_combo()
        self.shipping_method.currentIndexChanged.connect(lambda:refresh_shipping_accounts(settings,self.shipping_account,self.shipping_method))
        ship_form=QFormLayout();ship_form.setSpacing(6)
        ship_form.addRow('Forma de pago',self.shipping_method);ship_form.addRow('Pagado el',self.shipping_date);ship_form.addRow('Cuenta opcional',self.shipping_account)
        shipping.addLayout(ship_form);self.shipping_status=note('');shipping.addWidget(self.shipping_status);shipping.addStretch()
        self.summary=SaleSummary();root.addWidget(self.summary)
        self.error=note('','error');self.error.hide();root.addWidget(self.error)
        footer=QHBoxLayout();footer.addWidget(note('Marca los pagos realizados y guarda todos los cambios juntos.'),1)
        self.cancel_button=QPushButton('Anular venta');self.cancel_button.setObjectName('removeAction')
        footer.addWidget(self.cancel_button);self.cancel_button.clicked.connect(self.cancel_sale)
        self.delete_button=QPushButton('Eliminar');self.delete_button.setObjectName('removeAction')
        footer.addWidget(self.delete_button);self.delete_button.clicked.connect(self.delete_sale)
        self.history_button=QPushButton('Historial');footer.addWidget(self.history_button);self.history_button.clicked.connect(self.show_history)
        footer.addWidget(attachment_button(sales.connection,'sale',sale_id,self))
        close=QPushButton('Cerrar');self.save=QPushButton('Guardar cambios');self.save.setObjectName('primary')
        footer.addWidget(close);footer.addWidget(self.save);root.addLayout(footer)
        close.clicked.connect(self.reject);self.save.clicked.connect(self.persist)
        self.received.toggled.connect(self.update_state);self.shipping_paid.toggled.connect(self.update_state)
        self.withholding.toggled.connect(self.update_summary);self.commission.textChanged.connect(self.update_summary)
        self.shipping_account.currentIndexChanged.connect(self.update_state)
        self.load_saved_state();self.arrange_sections()

    @staticmethod
    def select_account(combo,key,name):
        index=combo.findData(key)
        if index<0 and key is not None:
            combo.addItem(name,key);index=combo.count()-1
        combo.setCurrentIndex(max(0,index))

    def load_saved_state(self):
        r=self.sale['receipt'];p=self.sale['shipping_payment']
        self.received.setChecked(bool(r));self.received.setEnabled(not r)
        if r:
            self.receipt_date.setDate(QDate.fromString(r['received_on'],'yyyy-MM-dd'))
            self.select_account(self.account,r['account_id'],r['account_name'])
            self.commission.setText(cents_text(r["commission_cents"]))
        self.shipping_paid.setChecked(bool(p));self.shipping_paid.setEnabled(not p and self.sale['shipping_cost_cents']>0)
        if p:
            self.shipping_date.setDate(QDate.fromString(p['paid_on'],'yyyy-MM-dd'))
            self.select_account(self.shipping_account,p['account_id'],p['account_name'])
            self.shipping_method.setCurrentIndex(self.shipping_method.findData(p['payment_kind']))
        self.update_state()
        self.apply_cancelled_state()

    def apply_cancelled_state(self):
        cancelled=bool(self.sale["cancelled_at"])
        self.cancelled_notice.setVisible(cancelled)
        permissions=self.sales.permissions()
        self.cancel_button.setVisible(not cancelled and permissions['cancel']);self.save.setVisible(not cancelled and permissions['edit'])
        self.edit_products.setEnabled(not cancelled and permissions['edit'])
        self.delete_button.setVisible(permissions['delete'])
        if cancelled:
            self.cancelled_notice.setText("ANULADA · Excluida de los totales. Motivo: "+(self.sale["cancellation_reason"] or "Sin especificar"))
        if cancelled or not permissions['edit']:
            for widget in (self.customer_alias,self.customer_phone,self.customer_email,self.invoice,self.withholding,self.tracking,self.received,self.receipt_date,self.account,self.commission,self.shipping_paid,self.shipping_date,self.shipping_method,self.shipping_account):widget.setEnabled(False)

    def edit_lines(self):
        from .sale_lines_dialog import SaleLinesDialog
        original=self.pending_lines or tuple(SaleLineInput(l['product_id'],l['quantity'],l['unit_price_cents']) for l in self.sale['lines'])
        dialog=SaleLinesDialog(self.sales.connection,original,self)
        if not self.sale['stock_tracked']:
            dialog.layout().insertWidget(1,note('Venta anterior al control de inventario: esta corrección no altera las existencias confirmadas.'))
        dialog.layout().insertWidget(1,note('Se conserva la tasa de IVA y comisión de esta venta. Si ya se cobró, se conserva la comisión real registrada.'))
        if dialog.exec()!=QDialog.Accepted:return
        self.pending_lines=dialog.result_lines
        self.products.clear()
        for line in self.pending_lines:
            p=self.sales.connection.execute('SELECT code,name FROM products WHERE id=?',(line.product_id,)).fetchone()
            self.products.addItem(f"{line.quantity} × {p['code']} · {p['name']} — {format_cop(line.quantity*line.unit_price_cents)}")
        self.update_summary()

    def delete_sale(self):
        answer=QMessageBox.warning(self,'Eliminar venta definitivamente',
            f'¿Eliminar la venta #{self.sale_id}, sus cobros, pagos e historial? Se revertirá su efecto en inventario y saldos. No se puede deshacer. Las copias físicas de documentos se conservan. Esto no anula la factura electrónica.',
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes:return
        try:
            self.sales.delete(self.sale_id);self.saved.emit(self.sale_id);self.accept()
        except StorageError as error:self.error.setText(str(error));self.error.show()

    def show_history(self):
        dialog=QDialog(self);dialog.setWindowTitle('Historial de cambios');dialog.resize(700,500)
        root=QVBoxLayout(dialog);text=QPlainTextEdit();text.setReadOnly(True);root.addWidget(text)
        entries=[]
        for row in self.sales.history(self.sale_id):
            before=json.loads(row['before_json']);after=json.loads(row['after_json'])
            entries.append(row['created_at']+'\nAntes: '+format_cop(before['total_cents'])+' → Después: '+format_cop(after['total_cents']))
            for title,data in [('Antes',before),('Después',after)]:
                entries.append(title+': '+ '; '.join(f"{l['quantity']} × {l['code']} · {l['name']} ({format_cop(l['unit_price_cents'])}/u)" for l in data['lines']))
            for key,label in [('invoice_ref','Factura'),('customer_email','Correo'),('customer_alias','Alias'),('customer_phone','Celular'),('has_withholding','Retención'),('tracking_number','Guía')]:
                if before[key]!=after[key]:entries.append(f"{label}: {before[key]} → {after[key]}")
        if self.sale['cancelled_at']:entries.append('Anulada: '+self.sale['cancelled_at']+' · '+(self.sale['cancellation_reason'] or 'Sin motivo'))
        text.setPlainText('\n'.join(entries) or 'Sin cambios registrados.')
        close=QPushButton('Cerrar');root.addWidget(close);close.clicked.connect(dialog.accept);dialog.exec()

    def preview_sale(self):
        result=dict(self.sale)
        if self.pending_lines is not None:
            totals=calculate_totals(self.pending_lines,self.sale['shipping_charged_cents'],self.sale['shipping_cost_cents'],
                Decimal(self.sale['rate_percent']),self.sale['fixed_cents'],vat_enabled=bool(self.sale['vat_enabled']),
                vat_rate=Decimal(self.sale['vat_rate']),vat_included=bool(self.sale['vat_included']))
            for field in ('subtotal_cents','total_cents','commission_cents','base_cents','vat_cents'):result[field]=getattr(totals,field)
        return result

    def cancel_sale(self):
        reason,accepted=QInputDialog.getText(self,"Anular venta",f"Anular la venta #{self.sale_id} la excluye de los totales y conserva su historial.\nNo modifica la factura en tu plataforma de facturación.\nMotivo (opcional):")
        if not accepted:return
        try:
            self.sale=self.sales.cancel(self.sale_id,reason)
            self.error.hide();self.load_saved_state();self.saved.emit(self.sale_id)
        except StorageError as e:
            self.error.setText(str(e));self.error.show()

    def update_state(self):
        r=self.sale['receipt'];p=self.sale['shipping_payment']
        for w in (self.receipt_date,self.account,self.commission):w.setEnabled(not r and self.received.isChecked())
        self.receipt_status.setText('Cobro registrado.' if r else ('Se registrará al guardar.' if self.received.isChecked() else 'Pendiente de recibir.'))
        enabled=self.sale['shipping_cost_cents']>0 and self.shipping_paid.isChecked()
        self.shipping_date.setEnabled(enabled and not p)
        for w in (self.shipping_account,self.shipping_method):w.setEnabled(enabled)
        self.shipping_status.setText('Sin costo de envío.' if not self.sale['shipping_cost_cents'] else ('Cuenta por completar; es opcional.' if enabled and self.shipping_account.currentData() is None else ('Pago registrado.' if p else ('Se registrará al guardar.' if enabled else 'Pendiente de pago. Puedes registrarlo después.'))))
        self.update_summary()

    def update_summary(self):
        try:
            sale=self.preview_sale()
            commission=money(self.commission.text()) if self.received.isChecked() else sale['commission_cents']
            if commission>sale['total_cents']:raise ValidationError({'comision':'La comisión supera el total.'})
            self.summary.update_amounts(sale['subtotal_cents'],sale['total_cents'],commission,sale['shipping_cost_cents'],self.received.isChecked(),self.withholding.isChecked(),withholding_deducted=bool(sale['withholding_deducted']),vat_enabled=bool(sale['vat_enabled']),vat_cents=sale['vat_cents'],base_cents=sale['base_cents'])
        except ValidationError as e:self.summary.setText(error_text(e))

    def arrange_sections(self):
        if not hasattr(self,'grid'):return
        columns=3 if self.width()>=1160 else 1
        while self.grid.count():self.grid.takeAt(0)
        for i in range(3):self.grid.setColumnStretch(i,1 if columns==3 else 0)
        for i,frame in enumerate(self.sections):self.grid.addWidget(frame,i//columns,i%columns)

    def resizeEvent(self,event):
        super().resizeEvent(event);self.arrange_sections()

    def _update_retention_requirement(self):
        needed=self.withholding.isChecked() and self.preferences.require_retention_documents()
        self.invoice_caption.setText('Factura electrónica *' if needed else 'Factura electrónica · opcional')
        self.email_caption.setText('Correo del cliente *' if needed else 'Correo del cliente · opcional')

    def persist(self):
        try:preview=self.preview_sale()
        except ValidationError as error:
            self.error.setText(error_text(error));self.error.show();return
        issues=[]
        if not self.sale['receipt'] and self.received.isChecked():
            issues=[choice(self.account,'la cuenta del cobro'),amount_issue(self.commission,'Comisión')]
            if not issues[1] and money(self.commission.text())>preview['total_cents']:issues.append((self.commission,'La comisión supera el total de la venta.'))
            if self.receipt_date.date().toString('yyyy-MM-dd')<self.sale['sold_on']:issues.append((self.receipt_date,'La recepción del dinero no puede ser anterior a la venta.'))
        self._update_retention_requirement()
        if self.withholding.isChecked() and self.preferences.require_retention_documents():
            issues.extend([required(self.invoice,'el número de factura para la retención'),required(self.customer_email,'el correo del cliente para la retención')])
        if not check(self,issues,self.error):return
        self.save.setEnabled(False)
        try:
            receipt=ReceiptInput(self.receipt_date.date().toPython(),self.account.currentData(),money(self.commission.text())) if not self.sale['receipt'] and self.received.isChecked() else None
            shipping=ShippingPaymentInput(self.shipping_date.date().toPython(),self.shipping_account.currentData(),self.shipping_method.currentData()) if not self.sale['shipping_payment'] and self.shipping_paid.isChecked() else None
            details=None;p=self.sale['shipping_payment']
            if p and (self.shipping_account.currentData(),self.shipping_method.currentData())!=(p['account_id'],p['payment_kind']):
                details=(self.shipping_account.currentData(),self.shipping_method.currentData())
            self.sale=self.sales.save_detail(self.sale_id,invoice_ref=self.invoice.text(),has_withholding=self.withholding.isChecked(),tracking_number=self.tracking.text(),customer_email=self.customer_email.text(),customer_alias=self.customer_alias.text(),customer_phone=self.customer_phone.text(),receipt=receipt,shipping_payment=shipping,shipping_details=details,lines=self.pending_lines)
            self.pending_lines=None
            self.error.hide();self.load_saved_state();self.saved.emit(self.sale_id);self.accept()
        except (StorageError,ValidationError) as e:
            self.error.setText(error_text(e));self.error.show()
        finally:self.save.setEnabled(True)
