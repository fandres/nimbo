from datetime import date
from dataclasses import replace
import pytest
from test_inventory_repository import ctx, start, buy, sell
from mi_negocio.fifo_repository import reconstruct_fifo
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput, PurchaseCostInput
from mi_negocio.purchases_repository import PurchasesRepository, draft_from_record
from mi_negocio.purchase_receipts_repository import PurchaseReceiptsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.sales import SaleLineInput
from mi_negocio.storage import StorageError


def valued_buy(cat, p, qty, cents, key):
    repo = PurchasesRepository(cat.connection)
    row = repo.create(PurchaseDraft(date.today(), 'Origen', '',
        (PurchaseLineInput(p.id, qty, cents),), costs_complete=True), request_id=key)
    receipt = PurchaseReceiptsRepository(cat.connection).receive(row['id'], date.today(), expected_revision=row['revision'])
    return repo.get(row['id']), receipt


def test_received_baseline_spanning_lots_and_late_cost(ctx):
    cat,p,s,inv=ctx
    row,a=valued_buy(cat,p,2,100,'a');start(inv,mode='receipts')
    valued_buy(cat,p,2,200,'b');sale=sell(cat,p,3)
    value=reconstruct_fifo(cat.connection).value(sale['id'],p.id)
    assert value['cost_cents']==400 and not value['provisional']
    draft=replace(draft_from_record(row),costs=(PurchaseCostInput('international_shipping','',60),))
    PurchasesRepository(cat.connection).update(row['id'],draft,expected_revision=row['revision'])
    assert reconstruct_fifo(cat.connection).value(sale['id'],p.id)['cost_cents']==460


def test_physical_baseline_and_untracked_sales_are_unknown(ctx):
    cat,p,s,inv=ctx
    old=sell(cat,p);valued_buy(cat,p,3,100,'a');start(inv,{p.id:3})
    sale=sell(cat,p,1,'new')
    ledger=reconstruct_fifo(cat.connection)
    assert ledger.value(old['id'],p.id)['cost_cents'] is None
    assert ledger.value(sale['id'],p.id)['cost_cents'] is None


def test_reversal_blocked_even_when_other_lot_covers_stock(ctx):
    cat,p,s,inv=ctx;start(inv)
    row,receipt=valued_buy(cat,p,2,100,'a');sale=sell(cat,p)
    valued_buy(cat,p,5,200,'b')
    with pytest.raises(StorageError,match='ventas'):
        PurchaseReceiptsRepository(cat.connection).reverse(receipt['id'],'Error',expected_revision=row['revision'])
    SalesRepository(cat.connection).cancel(sale['id'])
    PurchaseReceiptsRepository(cat.connection).reverse(receipt['id'],'Error',expected_revision=row['revision'])
    assert reconstruct_fifo(cat.connection).available(p.id)==5


def test_quantity_edits_restore_last_tranches(ctx):
    cat,p,s,inv=ctx;start(inv)
    valued_buy(cat,p,2,100,'a');valued_buy(cat,p,2,200,'b')
    sale=sell(cat,p,3);repo=SalesRepository(cat.connection)
    repo.save_detail(sale['id'],invoice_ref='',has_withholding=False,tracking_number='',lines=[SaleLineInput(p.id,1,100)])
    assert reconstruct_fifo(cat.connection).value(sale['id'],p.id)['cost_cents']==100
    other=sell(cat,p,3,'other')
    assert reconstruct_fifo(cat.connection).value(other['id'],p.id)['cost_cents']==500


def test_adjustments_and_historical_reversal(ctx):
    from mi_negocio.inventory_repository import move
    cat,p,s,inv=ctx;start(inv)
    row,receipt=valued_buy(cat,p,2,100,'a');sale=sell(cat,p)
    valued_buy(cat,p,4,200,'b')
    # An old reversal could pass the quantity-only guard. Replay must keep stock exact.
    with cat.connection:
        move(cat.connection,p.id,-2,f"reverse:{receipt['id']}",'reversal','Histórico')
        cat.connection.execute('UPDATE purchase_receipts SET reversed_at=? WHERE id=?',('2026-01-01',receipt['id']))
    ledger=reconstruct_fifo(cat.connection)
    assert ledger.available(p.id)==3
    assert ledger.value(sale['id'],p.id)['cost_cents'] is None
    inv.set_adjustments_enabled(True)
    inv.adjust(p.id,2,'Conteo',expected_revision=inv.state()['revision'])
    assert reconstruct_fifo(cat.connection).available(p.id)==2


def test_deleted_sales_return_lots_and_new_sale_does_not_reuse_id(ctx):
    cat,p,s,inv=ctx;start(inv);valued_buy(cat,p,2,100,'a')
    sale=sell(cat,p,2);repo=SalesRepository(cat.connection)
    repo.set_permission('delete',True);repo.delete(sale['id'])
    other=sell(cat,p,2,'other')
    ledger=reconstruct_fifo(cat.connection)
    assert other['id']>sale['id']
    assert ledger.value(other['id'],p.id)['cost_cents']==200
    assert ledger.available(p.id)==0


def test_fifo_received_date_and_registration_order(ctx):
    from datetime import timedelta
    cat,p,s,inv=ctx;start(inv)
    row,a=valued_buy(cat,p,2,100,'a')
    first=sell(cat,p,1,'first')
    row,b=valued_buy(cat,p,2,200,'b')
    with cat.connection:
        cat.connection.execute('UPDATE purchase_receipts SET received_on=? WHERE id=?',(str(date.today()-timedelta(days=1)),b['id']))
    second=sell(cat,p,2,'second')
    ledger=reconstruct_fifo(cat.connection)
    assert ledger.value(first['id'],p.id)['cost_cents']==100  # B did not exist at first sale
    assert ledger.value(second['id'],p.id)['cost_cents']==400


def test_purchase_vat_and_costs_included_only_once(ctx):
    cat,p,s,inv=ctx;start(inv);repo=PurchasesRepository(cat.connection)
    row=repo.create(PurchaseDraft(date.today(),'Proveedor','',
        (PurchaseLineInput(p.id,2,10000,vat_enabled=True),),
        costs=(PurchaseCostInput('international_shipping','',1000),),costs_complete=True),request_id='vat')
    PurchaseReceiptsRepository(cat.connection).receive(row['id'],date.today(),expected_revision=row['revision'])
    sale=sell(cat,p,2)
    assert reconstruct_fifo(cat.connection).value(sale['id'],p.id)['cost_cents']==24800


def test_positive_adjustment_unknown_and_mixed_purchase_unassigned(ctx):
    from mi_negocio.catalog import ProductInput,validate_product
    cat,p,s,inv=ctx
    other=cat.create(validate_product(ProductInput('OTHER','Otra máquina','product','100')))
    start(inv);repo=PurchasesRepository(cat.connection)
    row=repo.create(PurchaseDraft(date.today(),'Mixto','',
        (PurchaseLineInput(p.id,1,100),PurchaseLineInput(other.id,1,200)),
        costs=(PurchaseCostInput('international_shipping','',100),),costs_complete=True),request_id='mixed')
    PurchaseReceiptsRepository(cat.connection).receive(row['id'],date.today(),expected_revision=row['revision'])
    sale=sell(cat,p)
    value=reconstruct_fifo(cat.connection).value(sale['id'],p.id)
    assert value['cost_cents']==100 and value['provisional']
    inv.set_adjustments_enabled(True);inv.adjust(p.id,1,'Encontrada',expected_revision=inv.state()['revision'])
    adjusted=sell(cat,p,1,'adjusted')
    assert reconstruct_fifo(cat.connection).value(adjusted['id'],p.id)['cost_cents'] is None
