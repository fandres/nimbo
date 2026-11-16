from datetime import date
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.sales import SaleDraft, SaleLineInput
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.purchase_receipts_repository import PurchaseReceiptsRepository
from mi_negocio.inventory_repository import InventoryRepository
from mi_negocio.storage import StorageError

@pytest.fixture
def ctx(tmp_path):
    cat=CatalogRepository(tmp_path/'db')
    p=cat.create(validate_product(ProductInput('001','Máquina','product','100')))
    service=cat.create(validate_product(ProductInput('S','Servicio','service','50')))
    inv=InventoryRepository(cat.connection)
    yield cat,p,service,inv
    cat.close()

def start(inv,counts=None,mode='physical'):
    preview=inv.preview()
    inv.initialize(mode,counts or {r['id']:0 for r in preview['rows']},expected_token=preview['token'])

def buy(cat,p,qty=3,request='buy'):
    purchases=PurchasesRepository(cat.connection)
    row=purchases.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,qty,100),)),request_id=request)
    receipts=PurchaseReceiptsRepository(cat.connection)
    return receipts.receive(row['id'],date.today(),expected_revision=row['revision'])

def sell(cat,p,qty=1,request='sell',lines=None):
    method=SettingsRepository(cat.connection).list_methods()[0]
    return SalesRepository(cat.connection).create(SaleDraft(date.today(),'',tuple(lines or [SaleLineInput(p.id,qty,100)]),method.id,1,customer_name='Prueba'),request_id=request,expected_method=method)

def balance(inv,p):return next(r['available'] for r in inv.rows() if r['id']==p.id)

def test_physical_opening_ignores_history_and_old_cancel(ctx):
    cat,p,s,inv=ctx
    old=sell(cat,p,7);buy(cat,p,9)
    assert not inv.state()['initialized'] and balance(inv,p) is None
    start(inv,{p.id:3})
    assert balance(inv,p)==3
    SalesRepository(cat.connection).cancel(old['id'])
    assert balance(inv,p)==3
    with pytest.raises(StorageError):start(inv,{p.id:5})
    assert len(inv.history(p.id))==1

def test_received_opening_future_receipts_and_reversals(ctx):
    cat,p,s,inv=ctx
    old=buy(cat,p,3);start(inv,mode='receipts')
    assert balance(inv,p)==3
    with pytest.raises(StorageError):PurchaseReceiptsRepository(cat.connection).reverse(old['id'],'Error',expected_revision=2)
    new=buy(cat,p,2,'new')
    assert balance(inv,p)==5
    PurchaseReceiptsRepository(cat.connection).reverse(new['id'],'Error',expected_revision=2)
    assert balance(inv,p)==3

def test_stale_opening_rejected(ctx):
    cat,p,s,inv=ctx;preview=inv.preview();buy(cat,p)
    with pytest.raises(StorageError):inv.initialize('physical',{p.id:3},expected_token=preview['token'])
    assert not inv.state()['initialized']

def test_sale_aggregate_limit_retry_cancel_and_services(ctx):
    cat,p,s,inv=ctx;start(inv,{p.id:3})
    with pytest.raises(StorageError):sell(cat,p,lines=[SaleLineInput(p.id,2,100),SaleLineInput(p.id,2,100)])
    assert balance(inv,p)==3 and SalesRepository(cat.connection).list_sales()==[]
    sale=sell(cat,p,3);sell(cat,p,3)
    assert balance(inv,p)==0
    with pytest.raises(StorageError):sell(cat,p,1,'extra')
    sell(cat,s,500,'service')
    repo=SalesRepository(cat.connection);repo.cancel(sale['id']);repo.cancel(sale['id'])
    assert balance(inv,p)==3

def test_cannot_reverse_consumed_receipt(ctx):
    cat,p,s,inv=ctx;start(inv);receipt=buy(cat,p,3);sell(cat,p,2)
    with pytest.raises(StorageError):PurchaseReceiptsRepository(cat.connection).reverse(receipt['id'],'Error',expected_revision=2)
    assert balance(inv,p)==1
    assert PurchaseReceiptsRepository(cat.connection).current(receipt['purchase_id'])

def test_manual_adjustment_guard_revision_history(ctx):
    cat,p,s,inv=ctx;start(inv,{p.id:3});revision=inv.state()['revision']
    with pytest.raises(StorageError):inv.adjust(p.id,2,'Conteo',expected_revision=revision)
    inv.set_adjustments_enabled(True);revision=inv.state()['revision']
    for qty,reason in [(-1,'Motivo'),(1,''),(True,'Motivo')]:
        with pytest.raises(StorageError):inv.adjust(p.id,qty,reason,expected_revision=revision)
    inv.adjust(p.id,2,'Conteo físico',expected_revision=revision)
    assert balance(inv,p)==2 and inv.history(p.id)[-1]['reason']=='Conteo físico'
    with pytest.raises(StorageError):inv.adjust(p.id,9,'Ventana antigua',expected_revision=revision)
    inv.set_adjustments_enabled(False)
    with pytest.raises(StorageError):inv.adjust(p.id,9,'No habilitado',expected_revision=inv.state()['revision'])

def test_concurrent_last_unit(ctx,tmp_path):
    cat,p,s,inv=ctx;start(inv,{p.id:1});barrier=Barrier(2)
    def worker(key):
        other=CatalogRepository(tmp_path/'db')
        try:
            barrier.wait(timeout=5)
            try:sell(other,p,1,key);return True
            except StorageError:return False
        finally:other.close()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,['a','b']))
    assert sum(results)==1 and balance(inv,p)==0

def test_opening_completeness_and_kind_guard(ctx):
    cat,p,s,inv=ctx;preview=inv.preview()
    with pytest.raises(StorageError):inv.initialize('physical',{},expected_token=preview['token'])
    start(inv,{p.id:0})
    with pytest.raises(StorageError):cat.update(p.id,validate_product(ProductInput('001','Máquina','service','100')))

def test_migration_keeps_existing_sales_and_backs_up(tmp_path):
    cat=CatalogRepository(tmp_path/'legacy')
    for table in ['credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state']:cat.connection.execute('DROP TABLE '+table)
    cat.connection.execute('PRAGMA user_version=11');cat.connection.commit();cat.close()
    cat=CatalogRepository(tmp_path/'legacy')
    assert not InventoryRepository(cat.connection).state()['initialized']
    assert cat.connection.execute('PRAGMA user_version').fetchone()[0]==25
    assert list(tmp_path.glob('legacy.backup-*'));cat.close()


def test_adjustment_preview_is_invalidated_by_sale(ctx):
    cat,p,s,inv=ctx;start(inv,{p.id:3});inv.set_adjustments_enabled(True)
    preview=inv.adjustment_preview(p.id);sell(cat,p)
    with pytest.raises(StorageError):inv.adjust(p.id,2,'Conteo anterior',expected_revision=preview['revision'])
    assert balance(inv,p)==2


def test_downstream_payment_error_rolls_back_stock(ctx):
    from mi_negocio.sales import ReceiptInput
    cat,p,s,inv=ctx;start(inv,{p.id:3})
    method=SettingsRepository(cat.connection).list_methods()[0]
    draft=SaleDraft(date.today(),'',(SaleLineInput(p.id,1,100),),method.id,1,customer_name='Prueba')
    with pytest.raises(StorageError):SalesRepository(cat.connection).create(draft,request_id='bad',expected_method=method,receipt=ReceiptInput(date.today(),999,0))
    assert balance(inv,p)==3 and len(inv.history(p.id))==1
    assert not SalesRepository(cat.connection).list_sales()


def test_new_model_starts_at_zero_and_transit_is_not_stock(ctx):
    cat,p,s,inv=ctx;start(inv,{p.id:2})
    new=cat.create(validate_product(ProductInput('002','Otra','product','100')))
    PurchasesRepository(cat.connection).create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(new.id,5,100),)),request_id='transit')
    row=next(r for r in inv.rows() if r['id']==new.id)
    assert row['available']==0 and row['in_transit']==5
    with pytest.raises(StorageError):sell(cat,new)


def test_opening_stale_catalog_and_atomic_rollback(ctx):
    cat,p,s,inv=ctx;preview=inv.preview()
    cat.update(p.id,validate_product(ProductInput('001','Nuevo nombre','product','100')))
    with pytest.raises(StorageError):inv.initialize('receipts',{},expected_token=preview['token'])
    cat.connection.execute("CREATE TRIGGER reject_opening BEFORE INSERT ON inventory_movements BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(StorageError):start(inv,{p.id:1})
    assert not inv.state()['initialized'] and inv.history(p.id)==[]
