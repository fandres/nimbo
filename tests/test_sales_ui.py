from PySide6.QtCore import Qt
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.ui.sale_dialog import SaleDialog


def test_quick_sale_and_additional_reset(qtbot,tmp_path):
    catalog=CatalogRepository(tmp_path/'db')
    catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    settings=SettingsRepository(catalog.connection);sales=SalesRepository(catalog.connection)
    d=SaleDialog(catalog,settings,sales);qtbot.addWidget(d);d.show()
    d.customer.setText("Cliente de prueba");d.product.setCurrentIndex(1);qtbot.mouseClick(d.add_line,Qt.LeftButton)
    d.more.setChecked(True);d.extra_method.setCurrentIndex(d.extra_method.findData(4));assert d.selected_method.id==4
    d.more.setChecked(False);assert d.selected_method is None
    d.method_buttons[1].click();d.account.setCurrentIndex(1)
    qtbot.mouseClick(d.save,Qt.LeftButton)
    assert len(sales.list_sales())==1
    assert sales.list_sales()[0]['received']
    catalog.close()


def test_detail_confirms_receipt_and_shipping(qtbot,tmp_path):
    from datetime import date
    from mi_negocio.sales import SaleDraft,SaleLineInput
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    catalog=CatalogRepository(tmp_path/'db')
    p=catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    settings=SettingsRepository(catalog.connection);sales=SalesRepository(catalog.connection)
    m=settings.list_methods()[2]
    sale=sales.create(SaleDraft(date.today(),'FE',(SaleLineInput(p.id,1,100000000),),m.id,2,True,0,1000000,customer_name="Cliente de prueba"),request_id='x',expected_method=m)
    d=SaleDetailDialog(sale['id'],settings,sales);qtbot.addWidget(d);d.show()
    d.commission.setText('36000');d.received.setChecked(True)
    d.shipping_account.setCurrentIndex(1);d.shipping_paid.setChecked(True);d.save.click()
    assert sales.get(sale['id'])['receipt']['commission_cents']==3600000
    assert sales.get(sale['id'])['shipping_payment'] is not None
    assert not d.received.isEnabled()
    d.close();catalog.close()


def test_search_text_does_not_add_old_selection(qtbot,tmp_path):
    catalog=CatalogRepository(tmp_path/'db');catalog.create(validate_product(ProductInput('001','Máquina','product','100')))
    d=SaleDialog(catalog,SettingsRepository(catalog.connection),SalesRepository(catalog.connection));qtbot.addWidget(d)
    d.product.setCurrentIndex(1);d.product.setEditText('otra máquina inexistente');d.append_line()
    assert d.lines==[]
    catalog.close()


def test_shipping_form_fits_default_size(qtbot,tmp_path):
    from PySide6.QtWidgets import QApplication,QScrollArea
    catalog=CatalogRepository(tmp_path/'db')
    d=SaleDialog(catalog,SettingsRepository(catalog.connection),SalesRepository(catalog.connection));qtbot.addWidget(d);d.show()
    d.shipping.setChecked(True);d.more.setChecked(True)
    for _ in range(3):QApplication.processEvents()
    assert d.findChild(QScrollArea).verticalScrollBar().maximum()==0
    d.close();catalog.close()


def test_paid_shipping_and_small_window_keep_save_accessible(qtbot,tmp_path):
    from PySide6.QtWidgets import QApplication,QScrollArea
    catalog=CatalogRepository(tmp_path/'db')
    catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    d=SaleDialog(catalog,SettingsRepository(catalog.connection),SalesRepository(catalog.connection));qtbot.addWidget(d);d.show()
    d.product.setCurrentIndex(1);d.append_line();d.method_buttons[3].click()
    d.shipping.setChecked(True);d.shipping_paid.setChecked(True);d.more.setChecked(True);d.withholding.setChecked(True)
    for _ in range(3):QApplication.processEvents()
    scroll=d.findChild(QScrollArea)
    assert scroll.verticalScrollBar().maximum()==0
    d.resize(800,560)
    for _ in range(3):QApplication.processEvents()
    assert scroll.horizontalScrollBar().maximum()==0
    assert d.rect().contains(d.save.mapTo(d,d.save.rect().center()))
    d.close();catalog.close()


def test_failed_save_preserves_form_and_double_save_is_safe(qtbot,tmp_path,monkeypatch):
    from mi_negocio.storage import StorageError
    catalog=CatalogRepository(tmp_path/'db');catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    sales=SalesRepository(catalog.connection);d=SaleDialog(catalog,SettingsRepository(catalog.connection),sales);qtbot.addWidget(d);d.show()
    d.product.setCurrentIndex(1);d.append_line();d.method_buttons[1].click();d.account.setCurrentIndex(1);d.invoice.setText('FE-123');d.customer.setText('Cliente de prueba')
    original=sales.create
    def fail(*a,**kw):raise StorageError('Disco lleno')
    monkeypatch.setattr(sales,'create',fail);d.persist()
    assert d.isVisible() and len(d.lines)==1 and d.invoice.text()=='FE-123' and d.save.isEnabled()
    monkeypatch.setattr(sales,'create',original);d.persist();d.persist()
    assert len(sales.list_sales())==1
    catalog.close()


def test_transfer_accounts_and_cash_default(qtbot,tmp_path):
    from mi_negocio.sales import Account
    catalog=CatalogRepository(tmp_path/'db');settings=SettingsRepository(catalog.connection)
    nequi=settings.save_account(Account(0,'Nequi',True,'bank'))
    d=SaleDialog(catalog,settings,SalesRepository(catalog.connection));qtbot.addWidget(d)
    d.method_buttons[1].click()
    assert d.account.currentText()=='Efectivo'
    d.method_buttons[2].click()
    assert d.account.findText('Efectivo')==-1
    assert d.account.findData(nequi.id)>0
    d.account.setCurrentIndex(d.account.findData(nequi.id))
    assert d.account.currentText()=='Nequi'
    catalog.close()


def test_cash_selection_does_not_add_scrollbar(qtbot,tmp_path):
    from PySide6.QtWidgets import QApplication,QScrollArea
    catalog=CatalogRepository(tmp_path/'db')
    catalog.create(validate_product(ProductInput('10','Alpha Mk2 Algolaser 20W','product','3500000')))
    d=SaleDialog(catalog,SettingsRepository(catalog.connection),SalesRepository(catalog.connection));qtbot.addWidget(d);d.show()
    d.product.setCurrentIndex(1);d.append_line();d.method_buttons[1].click()
    for _ in range(5):QApplication.processEvents()
    assert d.received.isChecked()
    assert d.findChild(QScrollArea).verticalScrollBar().maximum()==0
    d.close();catalog.close()


def test_amount_first_click_selects_all(qtbot):
    from mi_negocio.ui.sales_widgets import amount
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget,QVBoxLayout,QLineEdit
    window=QWidget();layout=QVBoxLayout(window);other=QLineEdit();field=amount(2500000);layout.addWidget(other);layout.addWidget(field);qtbot.addWidget(window);window.show();other.setFocus()
    qtbot.mouseClick(field,Qt.LeftButton,pos=QPoint(15,10))
    assert field.selectedText()==field.text()
    qtbot.keyClicks(field,'18000')
    assert field.text()=='18000'


def test_product_search_has_placeholder_and_single_click_replaces(qtbot,tmp_path):
    from PySide6.QtCore import QPoint
    catalog=CatalogRepository(tmp_path/'db');catalog.create(validate_product(ProductInput('001','Máquina','product','100')))
    d=SaleDialog(catalog,SettingsRepository(catalog.connection),SalesRepository(catalog.connection));qtbot.addWidget(d);d.show()
    assert d.product.currentText()==''
    assert d.product.lineEdit().placeholderText()=='Busca por código o nombre'
    d.product.setCurrentIndex(1);d.customer.setFocus()
    qtbot.mouseClick(d.product.lineEdit(),Qt.LeftButton,pos=QPoint(20,10))
    qtbot.keyClicks(d.product.lineEdit(),'laser')
    assert d.product.currentText()=='laser'
    catalog.close()


def test_many_additional_methods_fit_expanded_height(qtbot,tmp_path):
    from decimal import Decimal
    from PySide6.QtWidgets import QApplication,QScrollArea
    from mi_negocio.sales import PaymentMethod
    catalog=CatalogRepository(tmp_path/'db');settings=SettingsRepository(catalog.connection)
    for i in range(12):settings.save_method(PaymentMethod(0,f'Plataforma {i}','',Decimal('1'),0,True,'additional',False))
    catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    d=SaleDialog(catalog,settings,SalesRepository(catalog.connection));qtbot.addWidget(d);d.resize(1230,780);d.show()
    d.product.setCurrentIndex(1);d.append_line();d.method_buttons[3].click();d.received.setChecked(True)
    d.shipping.setChecked(True);d.shipping_paid.setChecked(True);d.more.setChecked(True);d.withholding.setChecked(True)
    d.extra_method.setCurrentIndex(d.extra_method.count()-1);d.received.setChecked(True)
    assert d.selected_method.name=='Plataforma 11'
    d.carrier.setCurrentIndex(1)
    d.city.setText('Bogotá');d.tracking.setText('00123456')
    for _ in range(5):QApplication.processEvents()
    assert d.findChild(QScrollArea).verticalScrollBar().maximum()==0
    d.close();catalog.close()


def test_shipping_copies_charge_until_cost_manually_edited(qtbot,tmp_path):
    catalog=CatalogRepository(tmp_path/'db')
    d=SaleDialog(catalog,SettingsRepository(catalog.connection),SalesRepository(catalog.connection));qtbot.addWidget(d);d.show();d.shipping.setChecked(True)
    d.shipping_charged.setFocus();d.shipping_charged.selectAll();qtbot.keyClicks(d.shipping_charged,'42.500')
    assert d.shipping_cost.text()=='42.500'
    d.shipping_cost.setFocus();d.shipping_cost.selectAll();qtbot.keyClicks(d.shipping_cost,'50000')
    d.shipping_charged.setFocus();d.shipping_charged.selectAll();qtbot.keyClicks(d.shipping_charged,'40000')
    assert d.shipping_cost.text()=='50000'
    d.close();catalog.close()


def test_cost_only_does_not_charge_customer(qtbot,tmp_path):
    catalog=CatalogRepository(tmp_path/'db')
    d=SaleDialog(catalog,SettingsRepository(catalog.connection),SalesRepository(catalog.connection));qtbot.addWidget(d);d.show();d.shipping.setChecked(True)
    d.shipping_cost.selectAll();qtbot.keyClicks(d.shipping_cost,'42500')
    assert d.shipping_charged.text()=='0,00'
    d.close();catalog.close()


def test_amount_first_click_after_focus_already_assigned(qtbot):
    from mi_negocio.ui.sales_widgets import amount
    from PySide6.QtWidgets import QApplication
    field=amount();qtbot.addWidget(field);field.show();field.setFocus();QApplication.processEvents()
    qtbot.mouseClick(field,Qt.LeftButton)
    assert field.selectedText()=='0,00'


def test_shipping_tracking_and_grouped_totals(qtbot,tmp_path):
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    catalog=CatalogRepository(tmp_path/'db')
    catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    settings=SettingsRepository(catalog.connection);sales=SalesRepository(catalog.connection)
    d=SaleDialog(catalog,settings,sales);qtbot.addWidget(d)
    d.customer.setText('Cliente');d.product.setCurrentIndex(1);d.append_line()
    d.method_buttons[1].click();d.shipping.setChecked(True)
    d.shipping_charged.setText('42.500');d.shipping_cost.setText('50.000')
    d.invoice.setText('FE-123');d.customer_email.setText('cliente@example.com')
    d.tracking.setText('00123-ABC');d.withholding.setChecked(True)
    assert [v.text() for v in d.summary.values]==['$ 1.042.500,00','$ 50.000,00','$ 966.437,50']
    assert '$ 26.062,50' in d.summary.information.text()
    d.persist();assert d.saved_id is not None
    detail=SaleDetailDialog(d.saved_id,settings,sales);qtbot.addWidget(detail)
    assert detail.tracking.text()=='00123-ABC'
    detail.tracking.setText('000321-DEF');detail.persist()
    assert sales.get(d.saved_id)['tracking_number']=='000321-DEF'
    catalog.close()


def test_date_text_click_opens_calendar(qtbot):
    from mi_negocio.ui.sales_widgets import date_edit
    from PySide6.QtCore import QPoint
    field=date_edit();qtbot.addWidget(field);field.show()
    qtbot.mouseClick(field.lineEdit(),Qt.LeftButton,pos=QPoint(12,10))
    qtbot.waitUntil(lambda: field.calendarWidget().isVisible())
    target=field.date().addDays(-1)
    qtbot.keyClick(field.calendarWidget().focusWidget(),Qt.Key_Left)
    qtbot.keyClick(field.calendarWidget().focusWidget(),Qt.Key_Return)
    assert field.date()==target
    qtbot.waitUntil(lambda: not field.calendarWidget().isVisible())


def test_shipping_credit_without_account_then_complete_in_detail(qtbot,tmp_path):
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    catalog=CatalogRepository(tmp_path/'db')
    catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    settings=SettingsRepository(catalog.connection);sales=SalesRepository(catalog.connection)
    d=SaleDialog(catalog,settings,sales);qtbot.addWidget(d)
    d.customer.setText('Cliente');d.product.setCurrentIndex(1);d.append_line();d.method_buttons[1].click()
    d.shipping.setChecked(True);d.shipping_cost.setText('42.500');d.shipping_paid.setChecked(True)
    d.shipping_method.setCurrentIndex(d.shipping_method.findData('credit_card'))
    assert 'por completar' in d.shipping_hint.text()
    d.persist();assert d.saved_id is not None
    detail=SaleDetailDialog(d.saved_id,settings,sales);qtbot.addWidget(detail)
    assert 'Cuenta por completar' in detail.shipping_status.text()
    assert detail.shipping_method.currentData()=='credit_card'
    detail.shipping_account.setCurrentIndex(detail.shipping_account.findData(2));detail.shipping_paid.setChecked(True);detail.persist()
    assert sales.get(d.saved_id)['shipping_payment']['account_id']==2
    assert sales.get(d.saved_id)['shipping_payment']['payment_kind']=='credit_card'
    catalog.close()


def test_customer_contact_and_city_completion_survive_reopen(qtbot,tmp_path):
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    path=tmp_path/'db';catalog=CatalogRepository(path)
    catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    settings=SettingsRepository(catalog.connection);sales=SalesRepository(catalog.connection)
    d=SaleDialog(catalog,settings,sales);qtbot.addWidget(d)
    d.customer.setText('Cliente');d.customer_identification.setText('00123456-7');d.customer_email.setText('cliente@example.com')
    d.product.setCurrentIndex(1);d.append_line();d.method_buttons[1].click()
    d.shipping.setChecked(True);d.city.setText('Bogotá');d.shipping_cost.setText('42500');d.persist()
    key=d.saved_id;assert key is not None
    catalog.close();catalog=CatalogRepository(path)
    sales=SalesRepository(catalog.connection);settings=SettingsRepository(catalog.connection)
    saved=sales.get(key)
    assert saved['customer_identification']=='00123456-7'
    assert saved['customer_email']=='cliente@example.com'
    assert saved['shipping_payment'] is None
    next_sale=SaleDialog(catalog,settings,sales);qtbot.addWidget(next_sale)
    completer=next_sale.city.completer();completer.setCompletionPrefix('bog')
    assert completer.currentCompletion()=='Bogotá'
    detail=SaleDetailDialog(key,settings,sales);qtbot.addWidget(detail)
    assert '00123456-7' in detail.customer_info.text()
    assert 'cliente@example.com' in detail.customer_info.text()
    assert 'Pendiente de pago' in detail.shipping_status.text()
    detail.shipping_paid.setChecked(True);detail.persist()
    assert sales.get(key)['shipping_payment']['account_id'] is None
    catalog.close()


def test_detail_single_save_and_layout(qtbot,tmp_path):
    from datetime import date
    from PySide6.QtWidgets import QPushButton,QApplication
    from mi_negocio.sales import SaleDraft,SaleLineInput
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    catalog=CatalogRepository(tmp_path/'db')
    p=catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    settings=SettingsRepository(catalog.connection);sales=SalesRepository(catalog.connection);m=settings.list_methods()[2]
    sale=sales.create(SaleDraft(date.today(),'FE',(SaleLineInput(p.id,1,100000000),),m.id,2,True,0,4250000,customer_name='Cliente'),request_id='detail-layout',expected_method=m)
    d=SaleDetailDialog(sale['id'],settings,sales);qtbot.addWidget(d);d.resize(1230,760);d.show()
    d.received.setChecked(True);d.shipping_paid.setChecked(True)
    for _ in range(5):QApplication.processEvents()
    assert d.scroll.verticalScrollBar().maximum()==0
    assert [b.text() for b in d.findChildren(QPushButton) if b.accessibleName()!='Documentos adjuntos']==['Editar productos','Anular venta','Eliminar','Historial','Cerrar','Guardar cambios']
    d.received.setChecked(False);d.shipping_paid.setChecked(False)
    d.customer_email.setText('cliente@example.com')
    d.invoice.setText('FE-EDIT');d.tracking.setText('001234');d.withholding.setChecked(True);d.save.click()
    saved=sales.get(sale['id'])
    assert saved['invoice_ref']=='FE-EDIT' and saved['tracking_number']=='001234' and saved['has_withholding']
    assert saved['receipt'] is None and saved['shipping_payment'] is None
    catalog.close()


def test_cancel_confirmation_and_readonly_detail(qtbot,tmp_path,monkeypatch):
    from datetime import date
    from PySide6.QtWidgets import QInputDialog
    from mi_negocio.sales import SaleDraft,SaleLineInput
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    catalog=CatalogRepository(tmp_path/'db')
    p=catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    settings=SettingsRepository(catalog.connection);sales=SalesRepository(catalog.connection);m=settings.list_methods()[0]
    sale=sales.create(SaleDraft(date.today(),'FE',(SaleLineInput(p.id,1,100000000),),m.id,1,customer_name='Cliente'),request_id='cancel-ui',expected_method=m)
    d=SaleDetailDialog(sale['id'],settings,sales);qtbot.addWidget(d);d.show()
    monkeypatch.setattr(QInputDialog,'getText',lambda *args:('',False))
    d.cancel_button.click();assert sales.get(sale['id'])['cancelled_at'] is None
    monkeypatch.setattr(QInputDialog,'getText',lambda *args:('Duplicada',True))
    d.cancel_button.click()
    assert 'ANULADA' in d.cancelled_notice.text()
    assert not d.invoice.isEnabled() and not d.received.isEnabled() and not d.tracking.isEnabled()
    assert not d.save.isVisible() and not d.cancel_button.isVisible()
    catalog.close()
