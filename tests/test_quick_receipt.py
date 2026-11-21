from datetime import date,timedelta
from decimal import Decimal
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.storage import StorageError

@pytest.fixture
def setup(tmp_path):
    cat=CatalogRepository(tmp_path/'db');settings=SettingsRepository(cat.connection);sales=SalesRepository(cat.connection)
    product=cat.create(validate_product(ProductInput('1','Producto','product','10000')))
    method=settings.list_methods()[0]
    sale=sales.create(SaleDraft(date.today()-timedelta(days=2),'FE-1',(SaleLineInput(product.id,1,1000000),),method.id,1,customer_name='Cliente',has_withholding=True),request_id='sale',expected_method=method)
    yield cat,settings,sales,sale
    cat.close()

def test_quick_receipt_changes_method_and_keeps_retention(setup):
    cat,settings,sales,sale=setup
    method=settings.list_methods()[2]
    result=sales.confirm_receipt(sale['id'],ReceiptInput(date.today(),2,35900),payment_method=method,expected_sale=sale)
    assert result['method_id']==method.id
    assert result['receipt']['account_id']==2
    assert result['deposit_cents']==1000000-35900-25000
    assert sales.history(sale['id'])
    with pytest.raises(StorageError):sales.confirm_receipt(sale['id'],ReceiptInput(date.today(),2,35900),expected_sale=sale)

def test_quick_receipt_change_rolls_back_with_invalid_date(setup):
    _,settings,sales,sale=setup
    with pytest.raises(StorageError):sales.confirm_receipt(sale['id'],ReceiptInput(date.today()-timedelta(days=4),2,0),payment_method=settings.list_methods()[2],expected_sale=sale)
    assert sales.get(sale['id'])==sale

def test_quick_receipt_rejects_concurrent_edit(setup):
    _,settings,sales,sale=setup
    sales.update_invoice(sale['id'],'Changed')
    with pytest.raises(StorageError):sales.confirm_receipt(sale['id'],ReceiptInput(date.today(),1,0),expected_sale=sale)
    assert not sales.get(sale['id'])['received']

def test_quick_dialog_confirms_without_opening_detail(qtbot,setup):
    from mi_negocio.ui.sales_page import SalesPage
    from mi_negocio.ui.receipt_dialog import ReceiptDialog
    cat,settings,sales,sale=setup
    page=SalesPage(cat,settings,sales);qtbot.addWidget(page)
    page.open_sale_detail(sale['id'],collect=True)
    dialog=page.dialog;assert isinstance(dialog,ReceiptDialog);qtbot.addWidget(dialog)
    method=settings.list_methods()[2]
    dialog.method.setCurrentIndex(dialog.method.findData(method.id))
    dialog.account.setCurrentIndex(dialog.account.findData(2))
    assert money_text(dialog.commission.text())==125900
    assert '8.491,00' in dialog.summary.text()
    dialog.persist()
    assert sales.get(sale['id'])['received']
    assert sales.get(sale['id'])['method_id']==method.id

def money_text(text):
    from mi_negocio.sales import money
    return money(text)

def test_detail_can_change_pending_method_without_collecting(qtbot,setup):
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    _,settings,sales,sale=setup
    dialog=SaleDetailDialog(sale['id'],settings,sales);qtbot.addWidget(dialog)
    # Required retention data is supplied while saving the regular detail.
    dialog.customer_email.setText('cliente@example.com')
    method=settings.list_methods()[2]
    dialog.payment_method.setCurrentIndex(dialog.payment_method.findData(method.id))
    assert dialog.preview_sale()['commission_cents']==125900
    dialog.persist()
    result=sales.get(sale['id'])
    assert result['method_id']==method.id
    assert not result['received']
    dialog.close()

def test_detail_changed_bank_method_rejects_cash_receipt(setup):
    _,settings,sales,sale=setup
    from dataclasses import replace
    method=settings.save_method(replace(settings.list_methods()[2],account_kind='bank'))
    with pytest.raises(StorageError):
        sales.save_detail(sale['id'],invoice_ref=sale['invoice_ref'],has_withholding=True,tracking_number='',payment_method=method,receipt=ReceiptInput(date.today(),1,35900))
    assert sales.get(sale['id'])==sale

def test_changed_configuration_does_not_silently_change_fee(setup):
    from dataclasses import replace
    _,settings,sales,sale=setup
    method=settings.list_methods()[2]
    settings.save_method(replace(method,rate_percent=Decimal('8')))
    with pytest.raises(StorageError):sales.confirm_receipt(sale['id'],ReceiptInput(date.today(),2,35900),payment_method=method,expected_sale=sale)
    assert sales.get(sale['id'])==sale

def test_method_change_validates_final_retention_state(setup):
    from dataclasses import replace
    _,settings,sales,sale=setup
    method=settings.save_method(replace(settings.list_methods()[2],rate_percent=Decimal('98'),fixed_cents=0))
    result=sales.save_detail(sale['id'],invoice_ref=sale['invoice_ref'],has_withholding=False,tracking_number='',payment_method=method)
    assert result['commission_cents']==980000
    assert not result['has_withholding']

def test_quick_receipt_respects_disabled_edit_permission(setup):
    _,settings,sales,sale=setup
    sales.set_permission('edit',False)
    with pytest.raises(StorageError,match='deshabilitada'):
        sales.confirm_receipt(sale['id'],ReceiptInput(date.today(),1,0),expected_sale=sale)
    assert not sales.get(sale['id'])['received']
