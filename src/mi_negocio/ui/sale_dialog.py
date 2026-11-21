from .numeric_spinbox import NumericSpinBox as QSpinBox
"""Venta rápida: catálogo, cobro y envío en una sola revisión."""
from .vat_fields import VatFields
from ..vat import sale_line_amounts
from .completion import enable_unique_tab
from uuid import uuid4
from decimal import Decimal
from ..commissions import effective_fee,validate_fee
from dataclasses import replace
from PySide6.QtCore import Qt, Signal, QDate, QEvent, QTimer
from PySide6.QtWidgets import (QDialog,QFrame,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QGridLayout,QScrollArea,QPushButton,QComboBox,QCheckBox,QTableWidget,QTableWidgetItem,QHeaderView,QLineEdit,QButtonGroup,QAbstractItemView,QCompleter)
from .form_validation import check, required, choice, amount_issue, rate_issue
from ..sales import SaleLineInput,SaleDraft,ReceiptInput,ShippingPaymentInput,calculate_totals,money,informative_withholding
from ..catalog import ValidationError
from ..storage import StorageError
from .style import STYLE,format_cop
from .sale_summary import SaleSummary
from .preferences import DisplayPreferences
from .sales_widgets import note,amount,date_edit,account_combo,cents_text,error_text,ToggleSwitch,AmountEdit,shipping_method_combo


class SaleDialog(QDialog):
    saved=Signal(int)
    def __init__(self,catalog,settings,sales,parent=None,preferences=None):
        super().__init__(parent)
        self.preferences=preferences if preferences is not None else DisplayPreferences()
        self.catalog,self.settings,self.sales=catalog,settings,sales
        from ..inventory_repository import InventoryRepository
        self.inventory=InventoryRepository(catalog.connection)
        self.stock_ready=bool(self.inventory.state()["initialized"])
        self.stock={r["id"]:r["available"] for r in self.inventory.rows()}
        self.request_id=uuid4().hex;self.lines=[];self.selected_method=None
        self.state_touched=self.commission_touched=False;self.saved_id=None
        self.setWindowTitle('Nueva venta');self.setModal(True);self.resize(1440,900);self.setMinimumSize(760,460);self.setStyleSheet(STYLE)
        root=QVBoxLayout(self);root.setContentsMargins(24,18,24,18);root.setSpacing(16)
        root.addWidget(note('Nueva venta','heading'))
        self.columns=QHBoxLayout();self.columns.setSpacing(18);root.addLayout(self.columns,1)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.NoFrame)
        body=QWidget();body.setObjectName('saleBody');self.scroll.setWidget(body)
        left=QVBoxLayout(body);self.left_layout=left;left.setContentsMargins(0,0,0,0);left.setSpacing(16)
        self.columns.addWidget(self.scroll,7)
        self.right_scroll=QScrollArea();self.right_scroll.setWidgetResizable(True);self.right_scroll.setFrameShape(QFrame.NoFrame)
        right_body=QWidget();right_body.setObjectName('saleBody');right=QVBoxLayout(right_body);right.setContentsMargins(0,0,0,0);right.setSpacing(16)
        self.right_scroll.setWidget(right_body);self.columns.addWidget(self.right_scroll,3)
        def card(title,parent_layout):
            frame=QFrame();frame.setObjectName('saleSection');layout=QVBoxLayout(frame)
            layout.setContentsMargins(18,14,18,14);layout.setSpacing(10)
            if title:layout.addWidget(note(title,'cardTitle'))
            parent_layout.addWidget(frame)
            return frame,layout
        def field(title,widget):
            box=QVBoxLayout();box.setSpacing(4);box.addWidget(note(title,'fieldHeading'));box.addWidget(widget);return box
        self.identity,identity=card('Cliente',left)
        identity_fields=QHBoxLayout();identity_fields.setSpacing(16)
        self.customer=QLineEdit();self.customer.setPlaceholderText('Nombre o razón social del cliente');self.customer.setAccessibleName('Cliente obligatorio')
        identity_fields.addLayout(field('Cliente *',self.customer),3)
        self.sold_on=date_edit();self.sold_on.setMaximumWidth(180)
        date_field=QVBoxLayout();date_field.setSpacing(4);self.date_caption=note('Fecha de venta · Hoy','fieldHeading')
        date_field.addWidget(self.date_caption);date_field.addWidget(self.sold_on);identity_fields.addLayout(date_field)
        self.sold_on.dateChanged.connect(lambda value:self.date_caption.setText('Fecha de venta · Hoy' if value==QDate.currentDate() else 'Fecha de venta'))
        identity.addLayout(identity_fields)
        self.customer_more=QPushButton('+ Agregar cédula / NIT y correo');self.customer_more.setCheckable(True);self.customer_more.setObjectName('quietAction')
        customer_actions=QHBoxLayout();customer_actions.addWidget(self.customer_more)
        self.customer_extras_toggle=QPushButton('+ Alias / detalles y celular');self.customer_extras_toggle.setCheckable(True);self.customer_extras_toggle.setObjectName('quietAction')
        customer_actions.addWidget(self.customer_extras_toggle);customer_actions.addStretch();identity.addLayout(customer_actions)
        self.customer_details=QWidget();contact=QHBoxLayout(self.customer_details);contact.setContentsMargins(0,0,0,0)
        self.customer_identification=QLineEdit();self.customer_identification.setPlaceholderText('Número de documento')
        self.customer_email=QLineEdit();self.customer_email.setPlaceholderText('nombre@correo.com')
        for title,widget in [('Cédula / NIT · opcional',self.customer_identification),('Correo · opcional',self.customer_email)]:
            widget.setAccessibleName(title)
            if widget is self.customer_identification:
                contact_field=QVBoxLayout();contact_field.setSpacing(4);self.identification_caption=note(title,'fieldHeading');contact_field.addWidget(self.identification_caption);contact_field.addWidget(widget);contact.addLayout(contact_field)
            else:
                email_field=QVBoxLayout();email_field.setSpacing(4);self.email_caption=note(title,'fieldHeading');email_field.addWidget(self.email_caption);email_field.addWidget(widget);contact.addLayout(email_field)
        identity.addWidget(self.customer_details);self.customer_details.hide()
        self.customer_more.toggled.connect(self.customer_details.setVisible)
        self.customer_more.toggled.connect(lambda opened:self.customer_more.setText('Cédula / NIT y correo ▴' if opened else '+ Agregar cédula / NIT y correo'))
        self.customer_extras=QWidget();extras=QHBoxLayout(self.customer_extras);extras.setContentsMargins(0,0,0,0)
        self.customer_alias=QLineEdit();self.customer_alias.setPlaceholderText('Ej. Taller norte; llamar por la tarde')
        self.customer_phone=QLineEdit();self.customer_phone.setPlaceholderText('Ej. +57 300 123 4567')
        extras.addLayout(field('Alias o detalles · opcional',self.customer_alias),2);extras.addLayout(field('Celular · opcional',self.customer_phone),1)
        identity.addWidget(self.customer_extras);self.customer_extras.hide()
        self.customer_extras_toggle.toggled.connect(self.customer_extras.setVisible)
        self._update_identification_requirement()
        self.product_card,products=card('Productos',left)
        self.product=QComboBox();self.product.setEditable(True);self.product.setInsertPolicy(QComboBox.NoInsert);self.product.setLineEdit(AmountEdit())
        self.product.lineEdit().setPlaceholderText('Busca por código o nombre');self.product.setToolTip('Selecciona un producto y presiona Enter o Agregar.')
        self.product.addItem('',None);self.products={p.id:p for p in catalog.list_products(active=True)}
        for p in self.products.values():self.product.addItem(p.code+' · '+p.name,p.id)
        self.product.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.product.setMinimumContentsLength(12)
        self.product.completer().setCompletionMode(QCompleter.PopupCompletion);self.product.completer().setFilterMode(Qt.MatchContains);self.product.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.product.completer().activated[str].connect(self._completion_chosen)
        enable_unique_tab(self.product)
        search=QHBoxLayout();search.addWidget(self.product,1)
        self.add_line=QPushButton('+ Agregar');self.add_line.setObjectName('secondaryAction');search.addWidget(self.add_line);products.addLayout(search)
        self.vat=VatFields(self.preferences.vat_default('sales'));products.addWidget(self.vat)
        self.vat_hint=note('IVA sobre productos y servicios; el envío se registra por separado.');products.addWidget(self.vat_hint);self.vat_hint.setVisible(self.vat.enabled.isChecked())
        self.stock_hint=note('');products.addWidget(self.stock_hint)
        self.product.currentTextChanged.connect(self._stock_hint)
        self._stock_hint()
        self.product_editor=self.product.lineEdit();self.product_editor.installEventFilter(self)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['Producto','Cant.','Precio · COP','Total',''])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for col,width in [(1,70),(2,135),(3,135),(4,65)]:self.table.setColumnWidth(col,width)
        self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(125);self.table.setMaximumHeight(240);products.addWidget(self.table)
        self.products_hint=note('Los productos que agregues aparecerán aquí.');products.addWidget(self.products_hint)
        self.delivery_card,delivery_outer=card('',left)
        self.delivery_toggle=QPushButton('Factura y envío · opcional  ▾');self.delivery_toggle.setCheckable(True);self.delivery_toggle.setObjectName('quietAction')
        self.delivery_toggle.setStyleSheet('text-align: left; font-size: 16px; font-weight: 600; color: #162e50;')
        delivery_outer.addWidget(self.delivery_toggle)
        self.delivery_body=QWidget();delivery=QGridLayout(self.delivery_body);delivery.setContentsMargins(0,0,0,0);delivery.setHorizontalSpacing(12)
        delivery_outer.addWidget(self.delivery_body);self.delivery_body.hide();self.delivery_toggle.toggled.connect(self.delivery_body.setVisible)
        self.delivery_toggle.toggled.connect(lambda opened:self.delivery_toggle.setText('Factura y envío · opcional  '+('▴' if opened else '▾')))
        self.delivery_toggle.setChecked(True)
        left.addStretch()
        self.payment_card,payment=card('Pago',right)
        self.methods_box=QWidget();self.methods_layout=QGridLayout(self.methods_box);self.methods_layout.setContentsMargins(0,0,0,0);self.methods_layout.setSpacing(5)
        payment.addWidget(self.methods_box)
        self.more=QPushButton('Otro');self.more.setCheckable(True);self.more.setObjectName('paymentChoice')
        self.extra_box=QWidget();self.extra_layout=QGridLayout(self.extra_box);self.extra_layout.setContentsMargins(0,0,0,0);payment.addWidget(self.extra_box);self.extra_box.hide()
        self.extra_method=QComboBox();self.extra_method.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.extra_method.setMinimumContentsLength(12);self.extra_method.setAccessibleName('Plataforma adicional')
        self.extra_layout.addWidget(self.extra_method);self.extra_method.currentIndexChanged.connect(self.choose_extra_method)
        self.method_buttons={};self.method_group=QButtonGroup(self);self.method_group.setExclusive(True)
        self.method_info=note('Selecciona una forma de pago.');payment.addWidget(self.method_info)
        fee_row=QHBoxLayout();fee_row.addWidget(note('Ajustar comisión'),1)
        self.adjust_fee=ToggleSwitch('');self.adjust_fee.setAccessibleName('Ajustar comisión solo en esta venta');fee_row.addWidget(self.adjust_fee);payment.addLayout(fee_row)
        self.fee_fields=QWidget();fee_grid=QGridLayout(self.fee_fields);fee_grid.setContentsMargins(0,0,0,0);fee_grid.setSpacing(4)
        self.fee_rate=QLineEdit('0');self.fee_fixed=amount()
        fee_grid.addWidget(note('Porcentaje %'),0,0);fee_grid.addWidget(note('Cargo fijo · COP'),0,1);fee_grid.addWidget(self.fee_rate,1,0);fee_grid.addWidget(self.fee_fixed,1,1)
        payment.addWidget(self.fee_fields);self.fee_fields.hide()
        payment.addWidget(note('Cuenta de destino','fieldHeading'))
        account_row=QHBoxLayout();self.account=account_combo(settings);self.account.about_to_open.connect(self.refresh_account_options);account_row.addWidget(self.account,1)
        refresh=QPushButton('↻');refresh.setAccessibleName('Actualizar formas y cuentas');refresh.setToolTip('Actualizar formas de pago, cuentas y transportadoras');refresh.clicked.connect(self.reload_options);account_row.addWidget(refresh);payment.addLayout(account_row)
        separator=QFrame();separator.setFrameShape(QFrame.HLine);payment.addWidget(separator)
        receipt_heading=QHBoxLayout();receipt_heading.addWidget(note('Cobro recibido','fieldHeading'),1)
        self.received=ToggleSwitch('');self.received.setAccessibleName('Cobro recibido');receipt_heading.addWidget(self.received);payment.addLayout(receipt_heading)
        payment.addWidget(note('Actívalo si ya te llegó el dinero.'))
        self.receipt_date=date_edit();self.commission=amount();self.receipt_fields=QWidget();pay=QGridLayout(self.receipt_fields);pay.setContentsMargins(0,0,0,0);pay.setSpacing(4)
        pay.addWidget(note('Recibido el'),0,0);pay.addWidget(self.receipt_date,1,0);self.commission_caption=note('Comisión real · COP');pay.addWidget(self.commission_caption,0,1);pay.addWidget(self.commission,1,1)
        payment.addWidget(self.receipt_fields)
        invoice_frame = QFrame()
        invoice_frame.setObjectName('destinationGroup')
        invoice_layout = QVBoxLayout(invoice_frame)
        invoice_layout.setContentsMargins(8, 4, 8, 4)
        invoice_layout.setSpacing(4)
        invoice_layout.setAlignment(Qt.AlignTop)
        self.invoice_caption=note('Factura electrónica · opcional', 'fieldHeading');invoice_layout.addWidget(self.invoice_caption)
        self.invoice = QLineEdit()
        self.invoice.setPlaceholderText('Ej. FE-123')
        invoice_layout.addWidget(self.invoice)
        self.withholding=QCheckBox("Se aplicó retención")
        self.withholding.setToolTip("Descuenta el 2,5 % del depósito y lo registra en Retenciones de renta al confirmar el cobro.")
        retention_row=QHBoxLayout()
        retention_row.addWidget(self.withholding)
        retention_row.addWidget(note('(2,5 %)', 'muted'))
        retention_row.addStretch()
        invoice_layout.addLayout(retention_row)
        self.withholding_amount=note('','fieldHeading')
        self.withholding_amount.setStyleSheet('color: #244dc0; font-size: 14px; font-weight: 700;')
        self.withholding_amount.hide()
        invoice_layout.addWidget(self.withholding_amount)
        delivery.addWidget(invoice_frame, 0, 0)
        shipping_frame = QFrame()
        shipping_frame.setObjectName('shippingGroup')
        shipping_layout = QVBoxLayout(shipping_frame)
        shipping_layout.setContentsMargins(8, 4, 8, 4)
        shipping_layout.setSpacing(4)
        self.shipping = QCheckBox('Envío · esta venta tiene envío')
        shipping_layout.addWidget(self.shipping)
        delivery.addWidget(shipping_frame, 0, 1)
        self.shipping_box = QWidget()
        ship = QVBoxLayout(self.shipping_box)
        ship.setContentsMargins(0, 0, 0, 0)
        ship.setSpacing(3)
        self.shipping_charged = amount()
        self.shipping_cost = amount()
        self.shipping_cost_manual = False
        self.shipping_charged.textEdited.connect(self.copy_shipping_charge)
        self.shipping_cost.textEdited.connect(self.mark_shipping_cost_manual)
        self.shipping_cost.setToolTip("Copia el cobro al cliente hasta que edites este costo manualmente.")
        shipping_amounts = QHBoxLayout()
        for title, widget in [('Cobro al cliente · COP', self.shipping_charged), ('Costo del envío · COP', self.shipping_cost)]:
            field = QVBoxLayout()
            field.setSpacing(3)
            field.addWidget(note(title))
            field.addWidget(widget)
            shipping_amounts.addLayout(field)
        ship.addLayout(shipping_amounts)
        self.shipping_charged.setToolTip('Si el envío es gratuito para el cliente, deja este valor en cero.')
        self.shipping_hint = note('Pago pendiente; puedes registrarlo después.')
        ship.addWidget(self.shipping_hint)
        self.carrier = QComboBox()
        self.carrier.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.carrier.setMinimumContentsLength(10)
        self.city = QLineEdit()
        city_completer = QCompleter(self.sales.shipping_cities(), self.city)
        city_completer.setCaseSensitivity(Qt.CaseInsensitive)
        city_completer.setFilterMode(Qt.MatchStartsWith)
        self.city.setCompleter(city_completer)
        enable_unique_tab(self.city)
        self.city.setPlaceholderText('Ciudad de destino')
        shipping_details = QFormLayout()
        shipping_details.setSpacing(4)
        shipping_details.addRow('Transportadora', self.carrier)
        self.tracking = QLineEdit()
        self.tracking.setPlaceholderText('Guía (opcional)')
        self.tracking.setToolTip('Número de guía o tracking del envío · opcional')
        self.city.setToolTip('Ciudad de destino · opcional')
        self.tracking.setAccessibleName('Número de guía o tracking')
        self.city.setPlaceholderText('Ciudad (opcional)')
        shipping_details.addRow('Destino', self.city)
        shipping_details.addRow('Guía', self.tracking)
        self.shipping_details=QWidget();details_box=QVBoxLayout(self.shipping_details);details_box.setContentsMargins(0,0,0,0);details_box.addLayout(shipping_details)
        self.shipping_details_toggle=QPushButton('Transportadora, destino, guía y pago ▾');self.shipping_details_toggle.setCheckable(True);self.shipping_details_toggle.setObjectName('quietAction')
        ship.addWidget(self.shipping_details_toggle);ship.addWidget(self.shipping_details);self.shipping_details.hide();self.shipping_details_toggle.toggled.connect(self.shipping_details.setVisible)
        self.shipping_paid = QCheckBox('Ya pagué el envío')
        shipping_paid_row = QHBoxLayout()
        shipping_paid_row.addWidget(self.shipping_paid)
        self.shipping_method = shipping_method_combo()
        shipping_paid_row.addWidget(self.shipping_method, 1)
        details_box.addLayout(shipping_paid_row)
        self.shipping_date = date_edit()
        self.shipping_account = account_combo(settings)
        self.shipping_account.setItemText(0, 'Cuenta (opcional)')
        self.shipping_payment_box = QWidget()
        ship_payment = QHBoxLayout(self.shipping_payment_box)
        ship_payment.setContentsMargins(0, 0, 0, 0)
        self.shipping_date.setAccessibleName('Fecha de pago del envío')
        from .sales_widgets import refresh_shipping_accounts
        self.shipping_method.currentIndexChanged.connect(lambda:refresh_shipping_accounts(self.settings,self.shipping_account,self.shipping_method))
        self.shipping_account.setAccessibleName('Cuenta de pago o cuenta asociada a la tarjeta')
        self.shipping_account.setToolTip('Débito: cuenta de la que sale el dinero. Crédito: cuenta o tarjeta asociada al cargo; no representa una salida bancaria inmediata.')
        self.shipping_date.setMaximumWidth(125)
        ship_payment.addWidget(self.shipping_date)
        ship_payment.addWidget(self.shipping_account)
        details_box.addWidget(self.shipping_payment_box)
        shipping_layout.addWidget(self.shipping_box)
        self.shipping_box.hide()


        self.summary_card,summary_box=card('',right)
        self.summary=SaleSummary(vertical=True);summary_box.addWidget(self.summary)
        warning=note('Revisa los importes antes de guardar.');self.review_warning=warning;warning.setStyleSheet('background: #fff1d1; color: #925400; border-radius: 8px; padding: 8px;');summary_box.addWidget(warning)
        self.error=note('','error');self.error.hide();summary_box.addWidget(self.error)
        self.save=QPushButton('Guardar venta');self.save.setObjectName('primary');self.save.setMinimumHeight(44);summary_box.addWidget(self.save)
        cancel=QPushButton('Cancelar');cancel.setObjectName('quietAction');summary_box.addWidget(cancel)
        right.addStretch()
        self.summary_box=summary_box;self.cancel=cancel
        self.compact_footer=QWidget();self.compact_footer_layout=QHBoxLayout(self.compact_footer);self.compact_footer_layout.setContentsMargins(0,0,0,0)
        root.addWidget(self.compact_footer);self.compact_footer.hide();self._compact=False
        for button in self.findChildren(QPushButton):button.setAutoDefault(False)
        cancel.clicked.connect(self.reject);self.save.clicked.connect(self.persist);self.add_line.clicked.connect(self.append_line)
        self.more.toggled.connect(self.toggle_extra);self.shipping.toggled.connect(self.toggle_shipping)
        self.received.clicked.connect(self.touch_state);self.received.toggled.connect(self.payment_state);self.commission.textEdited.connect(self.touch_commission)
        self.adjust_fee.toggled.connect(self._adjust_fee)
        self.fee_rate.textChanged.connect(self._fee_edited);self.fee_fixed.textChanged.connect(self._fee_edited)
        self.vat.changed.connect(self._vat_changed)
        self.withholding.toggled.connect(self.recalculate)
        self.withholding.toggled.connect(self._update_retention_requirement)
        for widget in (self.shipping_charged,self.shipping_cost):widget.textChanged.connect(self.recalculate)
        self.shipping_paid.toggled.connect(self.shipping_state);self.shipping_account.currentIndexChanged.connect(self.shipping_state);self.shipping_method.currentIndexChanged.connect(self.shipping_state)
        self.reload_options();self.payment_state();self.shipping_state()

    def show_error(self, text):
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def _update_retention_requirement(self):
        needed=self.withholding.isChecked() and self.preferences.require_retention_documents()
        self.email_caption.setText('Correo *' if needed else 'Correo · opcional')
        self.invoice_caption.setText('Factura electrónica *' if needed else 'Factura electrónica · opcional')
        self.customer_email.setAccessibleName(self.email_caption.text())
        if needed:
            self.customer_more.setChecked(True)
            self.delivery_toggle.setChecked(True)
        self.customer_more.setEnabled(not (needed or self.preferences.require_sale_identification()))

    def _update_identification_requirement(self):
        required=self.preferences.require_sale_identification()
        self.identification_caption.setText('Cédula / NIT *' if required else 'Cédula / NIT · opcional')
        self.customer_identification.setAccessibleName(self.identification_caption.text())
        if required:self.customer_more.setChecked(True)
        self.customer_more.setEnabled(not required)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,'compact_footer'):return
        compact=self.height()<1000 or self.width()<1100
        if compact!=self._compact:
            self._compact=compact
            self.left_layout.setSpacing(8 if compact else 16)
            # Keep usable field width with native Windows scrollbars on small screens.
            for section in self.findChildren(QFrame, 'saleSection'):
                section.layout().setContentsMargins(12 if compact else 18,6 if compact else 14,12 if compact else 18,6 if compact else 14)
                section.layout().setSpacing(3 if compact else 10)
            target=self.compact_footer_layout if compact else self.summary_box
            target.addWidget(self.save);target.addWidget(self.cancel)
            self.compact_footer.setVisible(compact)
            self.review_warning.setVisible(not compact)

    def eventFilter(self,watched,event):
        if watched is getattr(self,"product_editor",None) and event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Return,Qt.Key_Enter):
            # Resolve completion first, then add once; Enter must never submit the dialog.
            self._queue_append()
            return True
        return super().eventFilter(watched,event)

    def _completion_chosen(self,text):
        index=self.product.findText(text,Qt.MatchExactly)
        if index>=0:self.product.setCurrentIndex(index);self._queue_append()

    def _queue_append(self):
        if getattr(self,'_add_pending',False):return
        self._add_pending=True
        QTimer.singleShot(0,self._finish_append)

    def _finish_append(self):
        self._add_pending=False;self.append_line()

    def append_line(self):
        text=self.product.currentText()
        key=next((key for key,p in self.products.items() if p.code+' · '+p.name==text),None)
        if key is None:
            check(self,[(self.product,'Selecciona un producto del catálogo.')],self.error);return
        if not check(self,[amount_issue(price,"Precio del producto") for quantity,price in getattr(self,'line_editors',[])],self.error):return
        try:self._validate_line_edits()
        except ValidationError as error:self.show_error(error_text(error));return
        try:
            self._reload_stock()
            if self.products[key].kind=='product' and self.stock_ready:
                remaining=self.stock.get(key,0)-sum(l.quantity for l in self.lines if l.product_id==key)
                if remaining<1:
                    self.show_error('No hay más unidades disponibles de este modelo.');return
        except StorageError as error:self.show_error(str(error));return
        self.lines.append(SaleLineInput(key,1,self.products[key].price_cop_cents))
        self.render_lines();self.show_error('')
        self.product.setCurrentIndex(0);self.product.lineEdit().clear();self.product.setFocus()

    def render_lines(self,price_texts=None):
        for row in range(self.table.rowCount()):
            for col in (1,2,4):
                widget=self.table.cellWidget(row,col)
                if widget:widget.hide()
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.lines));self.line_editors=[]
        self.table.setFixedHeight(54+54*max(1,min(3,len(self.lines))))
        for i,line in enumerate(self.lines):
            product=self.products[line.product_id]
            item=QTableWidgetItem(product.code+' · '+product.name);item.setToolTip(item.text());self.table.setItem(i,0,item)
            quantity=QSpinBox();quantity.setRange(1,999999);quantity.setValue(line.quantity);quantity.setAccessibleName('Cantidad de '+product.name)
            price=amount(line.unit_price_cents);price.setText(format_cop(line.unit_price_cents).replace('$ ',''));price.setAccessibleName('Precio de '+product.name)
            if price_texts is not None:price.setText(price_texts[i])
            self.table.setCellWidget(i,1,quantity);self.table.setCellWidget(i,2,price)
            remove=QPushButton('Quitar');remove.setObjectName('quietAction');remove.setAutoDefault(False);remove.setAccessibleName('Quitar '+product.name)
            self.table.setCellWidget(i,4,remove);remove.clicked.connect(lambda checked=False,row=i:self.remove_line(row))
            self.line_editors.append((quantity,price))
            quantity.valueChanged.connect(lambda value,row=i:self.update_line(row))
            price.textChanged.connect(lambda text,row=i:self.update_line(row))
            self._line_total(i)
        self._sync_stock_limits()
        self.products_hint.setVisible(not self.lines)
        self.table.setToolTip('Edita la cantidad o el precio directamente en la tabla.')
        self.recalculate()

    def _line_total(self,row):
        try:value=format_cop(sale_line_amounts(self.lines,self.vat.enabled.isChecked(),self.vat.values()['vat_rate'],self.vat.included.isChecked())[row])
        except ValidationError:value='Revisa el IVA'
        item=QTableWidgetItem(value);item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter);self.table.setItem(row,3,item)

    def update_line(self,row):
        try:
            quantity,price=self.line_editors[row]
            self.lines[row]=replace(self.lines[row],quantity=quantity.value(),unit_price_cents=money(price.text()))
            self._sync_stock_limits();self._line_total(row);self.recalculate();self.show_error('')
        except ValidationError as error:
            self.table.setItem(row,3,QTableWidgetItem('Revisa el precio'))
            self.summary.setText(error_text(error));self.show_error(error_text(error))
            self.update_withholding_amount()

    def remove_line(self,row):
        if 0<=row<len(self.lines):
            texts=[price.text() for quantity,price in getattr(self,'line_editors',[])]
            self.lines.pop(row);texts.pop(row);self.render_lines(texts);self.show_error('')

    def _reload_stock(self):
        self.stock_ready=bool(self.inventory.state()['initialized'])
        self.stock={r['id']:r['available'] for r in self.inventory.rows()}
        self._sync_stock_limits()

    def _sync_stock_limits(self):
        totals={}
        for line in self.lines:totals[line.product_id]=totals.get(line.product_id,0)+line.quantity
        for row,(quantity,price) in enumerate(getattr(self,'line_editors',[])):
            line=self.lines[row];product=self.products[line.product_id]
            if product.kind=='product' and self.stock_ready:
                available=self.stock.get(line.product_id,0) or 0
                maximum=max(1,available-totals[line.product_id]+line.quantity)
                quantity.blockSignals(True);quantity.setMaximum(max(quantity.value(),maximum));quantity.blockSignals(False)
                remaining=available-totals[line.product_id]
                item=self.table.item(row,0)
                item.setText(product.code+' · '+product.name+f'\nDisponible: {available} · Restante: {remaining}')
                from PySide6.QtGui import QColor
                item.setForeground(QColor('#b42332' if remaining<0 or available==0 else '#996000' if remaining<=2 else '#087544'))
                item.setToolTip(f'Disponible: {available} · En esta venta: {totals[line.product_id]} · Restante: {remaining}')
        self._stock_hint()

    def _stock_hint(self, *args):
        if not hasattr(self,'stock_hint'):return
        if not self.stock_ready:
            self.stock_hint.setText('Inventario sin configurar: esta venta no controla existencias. Configúralo desde Inventario.');return
        product=next((p for p in self.products.values() if p.code+' · '+p.name==self.product.currentText()),None)
        if product is None:self.stock_hint.setText('Stock controlado. Las cantidades se comprobarán otra vez al guardar.');return
        if product.kind=='service':self.stock_hint.setText('Servicio · sin límite de existencias');return
        stock=self.stock.get(product.id,0) or 0
        selected=sum(line.quantity for line in self.lines if line.product_id==product.id)
        self.stock_hint.setText(f'Disponibles: {stock} · En esta venta: {selected} · Restantes: {stock-selected}')

    def reload_options(self):
        try:
            methods=self.settings.list_methods()
            accounts=self.settings.list_accounts()
            carriers=self.settings.list_carriers()
        except StorageError as e:self.show_error(str(e));return
        for layout in (self.methods_layout,):
            while layout.count():
                item=layout.takeAt(0)
                if item.widget() is not self.more:self.method_group.removeButton(item.widget());item.widget().deleteLater()
        self.method_buttons={};self.selected_method=None;self.commission_touched=False
        self.adjust_fee.setChecked(False)
        self.extra_method.blockSignals(True)
        self.extra_method.clear()
        self.extra_method.addItem('Selecciona una plataforma',None)
        self.extra_methods = {}
        counts={'primary':0,'additional':0}
        for method in methods:
            if method.placement=='additional':
                self.extra_methods[method.id]=method
                self.extra_method.addItem(method.name,method.id)
                continue
            button=QPushButton(method.name);button.setStyleSheet('padding: 8px 6px; font-size: 12px;');button.setAutoDefault(False);button.setCheckable(True);button.setObjectName('paymentChoice');self.method_group.addButton(button)
            button.clicked.connect(lambda checked=False,m=method:self.choose_method(m))
            layout=self.methods_layout if method.placement=='primary' else self.extra_layout
            n=counts[method.placement];layout.addWidget(button,n//4,n%4);counts[method.placement]+=1;self.method_buttons[method.id]=button
        self.methods_layout.addWidget(self.more,counts['primary']//4,counts['primary']%4)
        self.extra_method.blockSignals(False)
        selected_carrier=self.carrier.currentData()
        self.carrier.clear();self.carrier.addItem("Sin especificar",None)
        for carrier in carriers:self.carrier.addItem(carrier["name"],carrier["id"])
        self.carrier.setCurrentIndex(max(0,self.carrier.findData(selected_carrier)))
        self.available_accounts = accounts
        for combo in (self.account,self.shipping_account):
            selected=combo.currentData();combo.clear();combo.addItem('Selecciona una cuenta',None)
            for account in accounts:combo.addItem(account.name,account.id)
            combo.setCurrentIndex(max(0,combo.findData(selected)))
        self.shipping_account.setItemText(0, 'Cuenta (opcional)')
        from .sales_widgets import refresh_shipping_accounts
        refresh_shipping_accounts(self.settings,self.shipping_account,self.shipping_method)
        self.method_info.setText('Selecciona una forma de pago.');self.payment_state();self.recalculate()

    def choose_extra_method(self):
        method = self.extra_methods.get(self.extra_method.currentData())
        if method:
            self.method_group.setExclusive(False)
            for button in self.method_buttons.values():
                button.setChecked(False)
            self.method_group.setExclusive(True)
            self.choose_method(method)
        elif self.selected_method and self.selected_method.placement == 'additional':
            self.selected_method = None
            self.filter_accounts()
            self.method_info.setText('Selecciona una forma de pago.')
            self.payment_state()

    def choose_method(self,method):
        if method.placement == 'primary':
            self.more.blockSignals(True);self.more.setChecked(False);self.more.blockSignals(False);self.extra_box.hide()
            self.extra_method.blockSignals(True)
            self.extra_method.setCurrentIndex(0)
            self.extra_method.blockSignals(False)
        self.selected_method=method;self.commission_touched=False
        self.adjust_fee.setChecked(False)
        self._fee(0)
        self.filter_accounts(propose=True)
        self.method_info.setText(f'{method.provider or method.name} · {method.rate_percent} % + {format_cop(method.fixed_cents)}')
        if not self.state_touched:self.received.setChecked(method.default_received)
        self.payment_state()
        self.recalculate()

    def refresh_account_options(self):
        try:
            self.available_accounts=self.settings.list_accounts()
        except StorageError as error:
            self.show_error(str(error));return
        self.filter_accounts()

    def filter_accounts(self, propose=False):
        previous = self.account.currentData()
        policy = self.selected_method.account_kind if self.selected_method else "any"
        accounts = [a for a in self.available_accounts if policy != "bank" or a.kind == "bank"]
        blocked=self.account.blockSignals(True)
        self.account.clear()
        self.account.addItem("Selecciona una cuenta", None)
        for account in accounts:
            self.account.addItem(account.name, account.id)
        default = next((a for a in accounts if a.kind == policy and a.is_default), None)
        if policy == "cash" and default is None:
            default = next((a for a in accounts if a.kind == "cash"), None)
        selected = default.id if propose and default else previous
        self.account.setCurrentIndex(max(0, self.account.findData(selected)))
        self.account.blockSignals(blocked)
        if not blocked and self.account.currentData()!=previous:
            self.account.currentIndexChanged.emit(self.account.currentIndex())

    def toggle_extra(self,visible):
        self.extra_box.setVisible(visible)
        if not visible:
            self.extra_method.setCurrentIndex(0)
        if not visible and self.selected_method and self.selected_method.placement=='additional':
            self.method_group.setExclusive(False)
            for b in self.method_buttons.values():b.setChecked(False)
            self.method_group.setExclusive(True);self.selected_method=None;self.filter_accounts();self.payment_state();self.method_info.setText('Selecciona una forma de pago.');self.recalculate()

    def copy_shipping_charge(self, text):
        if not self.shipping_cost_manual:
            self.shipping_cost.setText(text)

    def mark_shipping_cost_manual(self, text):
        self.shipping_cost_manual = True

    def toggle_shipping(self,visible):
        self.shipping_box.setVisible(visible)
        if not visible:self.shipping_paid.setChecked(False)
        self.recalculate()

    def shipping_state(self):
        if not self.shipping_paid.isChecked():
            hint = 'Pago pendiente; puedes registrarlo después.'
        elif self.shipping_account.currentData() is None:
            hint = 'Cuenta por completar en el detalle.'
        elif self.shipping_method.currentData() == 'unspecified':
            hint = 'Forma de pago por completar en el detalle.'
        else:
            hint = 'Pago registrado al guardar la venta.'
        self.shipping_hint.setText(hint)
        self.shipping_method.setVisible(self.shipping_paid.isChecked())
        self.shipping_payment_box.setVisible(self.shipping_paid.isChecked())
        for w in (self.shipping_date,self.shipping_account):w.setEnabled(self.shipping_paid.isChecked())

    def touch_state(self):self.state_touched=True
    def touch_commission(self):self.commission_touched=True;self.recalculate()
    def payment_state(self):
        self.receipt_fields.setVisible(self.received.isChecked())
        self.receipt_date.setEnabled(self.received.isChecked())
        self.commission.setEnabled(self.received.isChecked())
        charged = self.selected_method and (self.selected_method.rate_percent or self.selected_method.fixed_cents or self.selected_method.tiers or self.adjust_fee.isChecked())
        self.commission.setVisible(bool(charged))
        self.commission_caption.setVisible(bool(charged))
        self.recalculate()

    def _vat_changed(self):
        self.vat_hint.setVisible(self.vat.enabled.isChecked())
        self.recalculate()
        for row in range(len(self.lines)):self._line_total(row)

    def _adjust_fee(self,enabled):
        self.fee_fields.setVisible(enabled)
        self.commission_touched=False
        self.payment_state()

    def _fee_edited(self,*args):
        if self.adjust_fee.isChecked():
            self.commission_touched=False;self.recalculate()

    def _fee(self,total):
        if self.adjust_fee.isChecked():
            try:rate=Decimal(self.fee_rate.text().replace(',','.'))
            except ArithmeticError:raise ValidationError({'comision':'Escribe un porcentaje válido.'})
            fixed=money(self.fee_fixed.text());validate_fee(rate,fixed)
        else:
            rate,fixed=effective_fee(self.selected_method,total)
            for field,value in [(self.fee_rate,str(rate)),(self.fee_fixed,cents_text(fixed))]:
                field.blockSignals(True);field.setText(value);field.blockSignals(False)
        self.method_info.setText(f'{self.selected_method.provider or self.selected_method.name} · {rate} % + {format_cop(fixed)}'+(' · Ajuste para esta venta' if self.adjust_fee.isChecked() else ' · Automática'))
        return rate,fixed

    def totals(self):
        if not self.selected_method:raise ValidationError({'pago':'Selecciona una forma de pago.'})
        charged=money(self.shipping_charged.text()) if self.shipping.isChecked() else 0
        cost=money(self.shipping_cost.text()) if self.shipping.isChecked() else 0
        self._validate_line_edits()
        base=calculate_totals(tuple(self.lines),charged,cost,Decimal(0),0,**self.vat.values())
        rate,fixed=self._fee(base.total_cents)
        return calculate_totals(tuple(self.lines),charged,cost,rate,fixed,**self.vat.values())

    def _validate_line_edits(self):
        for line,(quantity,price) in zip(self.lines,getattr(self,'line_editors',[])):
            if money(price.text())!=line.unit_price_cents or quantity.value()!=line.quantity:
                raise ValidationError({'productos':'Revisa las cantidades y los precios.'})

    def update_withholding_amount(self):
        self.withholding_amount.setVisible(self.withholding.isChecked())
        if not self.withholding.isChecked():return
        try:
            self._validate_line_edits()
            charged=money(self.shipping_charged.text()) if self.shipping.isChecked() else 0
            totals=calculate_totals(tuple(self.lines),charged,0,Decimal(0),0,**self.vat.values())
            self.withholding_amount.setText('Valor retenido: '+format_cop(informative_withholding(totals.total_cents)))
        except ValidationError:
            self.withholding_amount.setText('Completa los importes para calcular la retención.')

    def recalculate(self):
        self.update_withholding_amount()
        try:
            t=self.totals()
            for row in range(min(len(self.lines),self.table.rowCount())):self._line_total(row)
            if not self.commission_touched:self.commission.setText(cents_text(t.commission_cents))
            actual=money(self.commission.text()) if self.received.isChecked() else t.commission_cents
            cost=money(self.shipping_cost.text()) if self.shipping.isChecked() else 0
            if actual>t.total_cents:raise ValidationError({'comision':'La comisión supera el total.'})
            self.summary.update_amounts(t.subtotal_cents,t.total_cents,actual,cost,self.received.isChecked(),self.withholding.isChecked(),vat_cents=t.vat_cents,base_cents=t.base_cents,vat_enabled=self.vat.enabled.isChecked())
        except ValidationError as e:self.summary.setText(error_text(e))

    def validate_fields(self):
        self._update_identification_requirement()
        self._update_retention_requirement()
        issues=[required(self.customer,'el nombre del cliente'),*self.vat.issues()]
        self.customer_identification._validation_reveal=lambda:self.customer_more.setChecked(True)
        if self.preferences.require_sale_identification():issues.append(required(self.customer_identification,'la cédula o NIT del cliente'))
        self.invoice._validation_reveal=lambda:self.delivery_toggle.setChecked(True)
        self.customer_email._validation_reveal=lambda:self.customer_more.setChecked(True)
        if self.withholding.isChecked() and self.preferences.require_retention_documents():
            issues.extend([required(self.invoice,'el número de factura para la retención'),required(self.customer_email,'el correo del cliente para la retención')])
        if not self.lines:issues.append((self.product,'Agrega al menos un producto o servicio a la venta.'))
        issues.extend(amount_issue(price,'Precio del producto') for quantity,price in getattr(self,'line_editors',[]))
        if not self.selected_method:issues.append((next(iter(self.method_buttons.values()),self.more),'Selecciona una forma de pago.'))
        issues.append(choice(self.account,'la cuenta de destino'))
        if self.adjust_fee.isChecked():issues.extend([rate_issue(self.fee_rate,'Comisión',100),amount_issue(self.fee_fixed,'Cargo fijo')])
        if self.received.isChecked():
            issues.append(amount_issue(self.commission,'Comisión'))
            if self.receipt_date.date()<self.sold_on.date():issues.append((self.receipt_date,'La recepción del dinero no puede ser anterior a la venta.'))
        if self.shipping.isChecked():
            for field,label in [(self.shipping_charged,'Cobro del envío'),(self.shipping_cost,'Costo del envío')]:
                field._validation_reveal=lambda:self.delivery_toggle.setChecked(True)
                issues.append(amount_issue(field,label,field is self.shipping_cost and self.shipping_paid.isChecked()))
        if not any(issues):
            total=self.totals()
            if self.received.isChecked() and money(self.commission.text())>total.total_cents:
                issues.append((self.commission,'La comisión supera el total de la venta.'))
        return check(self,issues,self.error)

    def persist(self):
        if self.saved_id is not None:return
        self.save.setEnabled(False)
        try:
            if not self.validate_fields():return
            self.totals()
            draft=SaleDraft(self.sold_on.date().toPython(),self.invoice.text(),tuple(self.lines),self.selected_method.id,self.account.currentData(),self.shipping.isChecked(),money(self.shipping_charged.text()) if self.shipping.isChecked() else 0,money(self.shipping_cost.text()) if self.shipping.isChecked() else 0,customer_name=self.customer.text(),carrier_id=self.carrier.currentData() if self.shipping.isChecked() else None,destination_city=self.city.text() if self.shipping.isChecked() else "",has_withholding=self.withholding.isChecked(),tracking_number=self.tracking.text() if self.shipping.isChecked() else "",customer_identification=self.customer_identification.text(),customer_email=self.customer_email.text(),customer_alias=self.customer_alias.text(),customer_phone=self.customer_phone.text(),**self.vat.values(),commission_override=self._fee(self.totals().total_cents) if self.adjust_fee.isChecked() else None)
            receipt=ReceiptInput(self.receipt_date.date().toPython(),self.account.currentData(),money(self.commission.text())) if self.received.isChecked() else None
            shipping=ShippingPaymentInput(self.shipping_date.date().toPython(),self.shipping_account.currentData(),self.shipping_method.currentData()) if self.shipping.isChecked() and self.shipping_paid.isChecked() else None
            result=self.sales.create(draft,request_id=self.request_id,expected_method=self.selected_method,receipt=receipt,shipping_payment=shipping)
            self.saved_id=result['id'];self.saved.emit(self.saved_id);self.accept()
        except (ValidationError,StorageError) as e:self.show_error(error_text(e))
        finally:self.save.setEnabled(self.saved_id is None)
