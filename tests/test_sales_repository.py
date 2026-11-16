from datetime import date, timedelta
from dataclasses import replace
from decimal import Decimal
import pytest
from mi_negocio.repository import CatalogRepository, StorageError
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.sales import *
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.settings_repository import SettingsRepository

@pytest.fixture
def setup(tmp_path):
    catalog=CatalogRepository(tmp_path/'db')
    p=catalog.create(validate_product(ProductInput('001','Máquina','product','1000000')))
    settings=SettingsRepository(catalog.connection)
    repo=SalesRepository(catalog.connection)
    method=settings.list_methods()[2]
    draft=SaleDraft(date.today()-timedelta(days=3),'FE-1',(SaleLineInput(p.id,1,100000000),),method.id,2,True,2000000,2500000,customer_name="Cliente de prueba")
    yield catalog,settings,repo,method,draft
    catalog.close()


def test_receipt_shipping_history_and_replay(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='a',expected_method=method)
    assert sale['receipt'] is None
    assert repo.home_summary(date.today())['pending_total_cents']==102000000
    assert repo.create(draft,request_id='a',expected_method=method)['id']==sale['id']
    settings.save_method(replace(method,rate_percent=Decimal('1'),enabled=False))
    sale=repo.confirm_receipt(sale['id'],ReceiptInput(date.today(),2,4000000))
    assert sale['deposit_cents']==98000000
    sale=repo.pay_shipping(sale['id'],ShippingPaymentInput(date.today(),1))
    assert sale['deposit_cents']==98000000
    assert sale['net_after_shipping_cents']==95500000
    assert sale['rate_percent']=='3.59'
    assert sale['lines'][0]['code']=='001'
    with pytest.raises(StorageError): repo.confirm_receipt(sale['id'],ReceiptInput(date.today(),2,4000000))
    with pytest.raises(StorageError): repo.pay_shipping(sale['id'],ShippingPaymentInput(date.today(),1))
    assert repo.home_summary(date.today())['pending_count']==0


def test_atomic_failure_and_changed_method(setup):
    cat,settings,repo,method,draft=setup
    settings.save_method(replace(method,rate_percent=Decimal('2')))
    with pytest.raises(StorageError): repo.create(draft,request_id='a',expected_method=method)
    assert repo.list_sales(SalesFilter())==[]
    method=settings.list_methods()[2]
    with pytest.raises(StorageError): repo.create(draft,request_id='b',expected_method=method,receipt=ReceiptInput(date.today(),999,0))
    assert repo.list_sales(SalesFilter())==[]


def test_filters_and_idempotency_conflict(setup):
    cat,settings,repo,method,draft=setup
    repo.create(draft,request_id='a',expected_method=method)
    assert len(repo.list_sales(SalesFilter(query='001',received=False,account_id=2)))==1
    assert repo.list_sales(SalesFilter(received=True))==[]
    assert repo.list_sales(SalesFilter(start=date.today()))==[]
    with pytest.raises(StorageError): repo.create(replace(draft,invoice_ref='x'),request_id='a',expected_method=method)


def test_two_connections_cannot_duplicate_receipt(setup,tmp_path):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='a',expected_method=method)
    other=CatalogRepository(tmp_path/'db')
    try:
        repo.confirm_receipt(sale['id'],ReceiptInput(date.today(),1,0))
        with pytest.raises(StorageError):SalesRepository(other.connection).confirm_receipt(sale['id'],ReceiptInput(date.today(),1,0))
        assert cat.connection.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]==1
    finally:other.close()


def test_failure_mid_lines_rolls_back(setup):
    cat,settings,repo,method,draft=setup
    bad=replace(draft,lines=draft.lines+(SaleLineInput(999,1,100),))
    with pytest.raises(StorageError):repo.create(bad,request_id='bad',expected_method=method)
    assert cat.connection.execute('SELECT COUNT(*) FROM sales').fetchone()[0]==0
    assert cat.connection.execute('SELECT COUNT(*) FROM sale_lines').fetchone()[0]==0


def test_product_edits_do_not_change_sale(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='a',expected_method=method)
    cat.update(draft.lines[0].product_id,validate_product(ProductInput('002','Otro','product','1')))
    assert repo.get(sale['id'])['lines'][0]['name']=='Máquina'


def test_invalid_receipt_date_and_commission_leave_pending(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='a',expected_method=method)
    for receipt in [ReceiptInput(draft.sold_on-timedelta(days=1),1,0),ReceiptInput(date.today()+timedelta(days=1),1,0),ReceiptInput(date.today(),1,102000001)]:
        with pytest.raises(StorageError):repo.confirm_receipt(sale['id'],receipt)
    assert repo.get(sale['id'])['receipt'] is None


def test_customer_carrier_snapshot_and_withholding(setup):
    cat,settings,repo,method,draft=setup
    carrier=settings.list_carriers()[0]
    draft=replace(draft,customer_name='Cliente Pérez',carrier_id=carrier['id'],destination_city='Bogotá',has_withholding=True)
    sale=repo.create(draft,request_id='retained',expected_method=method)
    settings.save_carrier(carrier['id'],'Otro nombre',False)
    assert repo.get(sale['id'])['carrier_name']==carrier['name']
    assert sale['destination_city']=='Bogotá'
    assert sale['total_cents']==102000000
    assert sale['deposit_cents']==95698200
    assert len(repo.list_sales(SalesFilter(query='pérez',has_withholding=True)))==1
    assert repo.list_sales(SalesFilter(has_withholding=False))==[]


def test_customer_required(setup):
    from mi_negocio.catalog import ValidationError
    cat,settings,repo,method,draft=setup
    with pytest.raises(ValidationError):repo.create(replace(draft,customer_name=' '),request_id='x',expected_method=method)
    assert repo.list_sales()==[]


def test_withholding_can_be_marked_later_with_deposit_deduction(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='mark-later',expected_method=method)
    repo.update_invoice(sale['id'],'FE-CERT',True)
    after=repo.get(sale['id'])
    assert after['invoice_ref']=='FE-CERT' and after['has_withholding']
    assert after['deposit_cents']==sale['deposit_cents']-after['withholding_cents']
    assert len(repo.list_sales(SalesFilter(start=draft.sold_on,end=date.today(),has_withholding=True)))==1


def test_withholding_includes_shipping_and_reduces_deposit(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(replace(draft,has_withholding=True),request_id='retention-value',expected_method=method)
    assert sale['withholding_cents']==2550000
    assert sale['deposit_cents']==95698200
    assert repo.list_sales(SalesFilter(has_withholding=True))[0]['withholding_cents']==2550000


def test_tracking_preserves_leading_zero_and_can_be_added_later(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(replace(draft,tracking_number='001234-AB'),request_id='tracked',expected_method=method)
    assert repo.get(sale['id'])['tracking_number']=='001234-AB'
    repo.update_tracking(sale['id'],'000987-Z')
    assert repo.get(sale['id'])['tracking_number']=='000987-Z'


@pytest.mark.parametrize('kind',['debit_card','credit_card','unspecified'])
def test_shipping_payment_without_account_can_be_completed(setup,kind):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='pending-shipping',expected_method=method)
    assert sale['shipping_payment'] is None
    paid=repo.pay_shipping(sale['id'],ShippingPaymentInput(date.today(),None,kind))
    assert paid['shipping_payment']['account_id'] is None
    assert paid['shipping_payment']['payment_kind']==kind
    completed=repo.update_shipping_payment_details(sale['id'],2,'debit_card')
    assert completed['shipping_payment']['account_id']==2
    assert completed['shipping_payment']['paid_on']==paid['shipping_payment']['paid_on']
    assert completed['total_cents']==sale['total_cents']
    assert cat.connection.execute('SELECT COUNT(*) FROM shipping_payments WHERE sale_id=?',(sale['id'],)).fetchone()[0]==1


def test_shipping_rejects_invalid_payment_kind(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='invalid-shipping',expected_method=method)
    with pytest.raises(StorageError):repo.pay_shipping(sale['id'],ShippingPaymentInput(date.today(),None,'invalid'))
    assert repo.get(sale['id'])['shipping_payment'] is None


def test_v6_upgrade_preserves_existing_sale_and_shipping_payment(setup,tmp_path):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='before-upgrade',expected_method=method,shipping_payment=ShippingPaymentInput(date.today(),2))
    with cat.connection:
        cat.connection.execute('ALTER TABLE sales DROP COLUMN customer_identification')
        cat.connection.execute('ALTER TABLE sales DROP COLUMN customer_email')
        cat.connection.execute('ALTER TABLE shipping_payments DROP COLUMN payment_kind')
        cat.connection.execute('ALTER TABLE sales DROP COLUMN cancelled_at')
        cat.connection.execute('ALTER TABLE sales DROP COLUMN cancellation_reason')
        for table in ('receipt_lines','purchase_receipts','purchase_revisions','purchase_costs','purchase_lines','purchases'):
            cat.connection.execute('DROP TABLE '+table)
        for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): cat.connection.execute('DROP TABLE IF EXISTS '+table)
        cat.connection.execute('PRAGMA user_version=6')
    cat.close()
    upgraded=CatalogRepository(tmp_path/'db')
    after=SalesRepository(upgraded.connection).get(sale['id'])
    assert after['shipping_payment']['account_id']==2
    assert after['shipping_payment']['payment_kind']=='account'
    assert after['customer_identification']==after['customer_email']==''
    assert after['total_cents']==sale['total_cents']
    assert list(tmp_path.glob('*.backup-*'))
    upgraded.close()


def test_detail_save_rolls_back_every_change_when_shipping_is_invalid(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='atomic-detail',expected_method=method)
    with pytest.raises(StorageError):
        repo.save_detail(sale['id'],invoice_ref='FE-NEW',has_withholding=True,tracking_number='00123',
            receipt=ReceiptInput(date.today(),2,100),shipping_payment=ShippingPaymentInput(date.today(),999999,'debit_card'))
    after=repo.get(sale['id'])
    assert after['receipt'] is None and after['shipping_payment'] is None
    assert after['invoice_ref']==sale['invoice_ref']
    assert not after['has_withholding'] and after['tracking_number']==''
    saved=repo.save_detail(sale['id'],invoice_ref='FE-NEW',has_withholding=True,tracking_number='00123',
        receipt=ReceiptInput(date.today(),2,100),shipping_payment=ShippingPaymentInput(date.today(),None,'credit_card'))
    assert saved['receipt'] and saved['shipping_payment']
    assert saved['invoice_ref']=='FE-NEW' and saved['has_withholding'] and saved['tracking_number']=='00123'


def test_cancel_preserves_history_excludes_totals_and_blocks_changes(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(replace(draft,has_withholding=True),request_id='cancel-sale',expected_method=method,
        receipt=ReceiptInput(date.today(),2,100),shipping_payment=ShippingPaymentInput(date.today(),None,'credit_card'))
    cancelled=repo.cancel(sale['id'],'Venta duplicada')
    assert cancelled['cancelled_at'] and cancelled['cancellation_reason']=='Venta duplicada'
    assert cancelled['lines']==sale['lines']
    assert cancelled['receipt']==sale['receipt'] and cancelled['shipping_payment']==sale['shipping_payment']
    assert repo.list_sales()==[] and repo.list_sales(SalesFilter(has_withholding=True))==[]
    assert len(repo.list_sales(SalesFilter(cancelled=True)))==1
    assert len(repo.list_sales(SalesFilter(cancelled=None)))==1
    summary=repo.home_summary(date.today())
    assert summary['month_subtotal_cents']==summary['pending_total_cents']==0 and summary['recent_sales']==[]
    assert repo.cancel(sale['id'],'Otro motivo')['cancellation_reason']=='Venta duplicada'
    actions=[lambda:repo.update_invoice(sale['id'],'CHANGED'),lambda:repo.update_tracking(sale['id'],'123'),
        lambda:repo.update_shipping_payment_details(sale['id'],2,'account'),
        lambda:repo.save_detail(sale['id'],invoice_ref='CHANGED',has_withholding=False,tracking_number='123')]
    for action in actions:
        with pytest.raises(StorageError,match='anulada'):action()
    assert repo.get(sale['id'])==cancelled


def test_cancel_pending_sale_blocks_receipt_and_shipping(setup):
    cat,settings,repo,method,draft=setup
    sale=repo.create(draft,request_id='cancel-pending',expected_method=method)
    repo.cancel(sale['id'])
    with pytest.raises(StorageError,match='anulada'):repo.confirm_receipt(sale['id'],ReceiptInput(date.today(),2,0))
    with pytest.raises(StorageError,match='anulada'):repo.pay_shipping(sale['id'],ShippingPaymentInput(date.today(),None))
    assert repo.home_summary(date.today())['pending_count']==0


def test_v7_upgrade_preserves_credit_payment_and_customer(setup,tmp_path):
    cat,settings,repo,method,draft=setup
    sale=repo.create(replace(draft,customer_identification='001234'),request_id='v7-sale',expected_method=method,shipping_payment=ShippingPaymentInput(date.today(),None,'credit_card'))
    with cat.connection:
        cat.connection.execute('ALTER TABLE sales DROP COLUMN cancelled_at')
        cat.connection.execute('ALTER TABLE sales DROP COLUMN cancellation_reason')
        for table in ('receipt_lines','purchase_receipts','purchase_revisions','purchase_costs','purchase_lines','purchases'):
            cat.connection.execute('DROP TABLE '+table)
        for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): cat.connection.execute('DROP TABLE IF EXISTS '+table)
        cat.connection.execute('PRAGMA user_version=7')
    cat.close();upgraded=CatalogRepository(tmp_path/'db')
    after=SalesRepository(upgraded.connection).get(sale['id'])
    assert after['shipping_payment']['payment_kind']=='credit_card'
    assert after['customer_identification']=='001234' and after['cancelled_at'] is None
    upgraded.close()
