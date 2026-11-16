from datetime import date,timedelta
from dataclasses import replace
import pytest
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput
from mi_negocio.purchases_repository import PurchasesRepository,draft_from_record
from mi_negocio.purchase_receipts_repository import PurchaseReceiptsRepository
from mi_negocio.storage import StorageError


@pytest.fixture
def context(tmp_path):
    cat=CatalogRepository(tmp_path/'db');p=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    repo=PurchasesRepository(cat.connection);receipts=PurchaseReceiptsRepository(cat.connection)
    row=repo.create(PurchaseDraft(date.today()-timedelta(days=1),'Proveedor','',
        (PurchaseLineInput(p.id,2,100),PurchaseLineInput(p.id,1,200))),request_id='one')
    yield cat,repo,receipts,row
    cat.close()


def test_receive_reverse_and_receive_again(context):
    cat,repo,receipts,row=context
    r=receipts.receive(row['id'],date.today(),expected_revision=1)
    assert sum(l['quantity'] for l in r['lines'])==3
    assert receipts.receive(row['id'],date.today(),expected_revision=1)['id']==r['id']
    assert repo.get(row['id'])['revision']==2
    with pytest.raises(StorageError):receipts.receive(row['id'],date.today()-timedelta(days=1),expected_revision=2)
    receipts.reverse(r['id'],'Error',expected_revision=2)
    assert receipts.current(row['id']) is None
    r2=receipts.receive(row['id'],date.today(),expected_revision=3)
    assert r2['id']!=r['id'] and len(receipts.history(row['id']))==2
    assert repo.get(row['id'])['received_quantity']==3


def test_received_purchase_guards(context):
    cat,repo,receipts,row=context
    receipts.receive(row['id'],date.today(),expected_revision=1)
    d=draft_from_record(repo.get(row['id']))
    for bad in (replace(d,lines=d.lines[:1]),replace(d,lines=(replace(d.lines[0],quantity=9),d.lines[1]))):
        with pytest.raises(StorageError):repo.update(row['id'],bad,expected_revision=2)
    with pytest.raises(StorageError):repo.cancel(row['id'],'error',expected_revision=2)
    result=repo.update(row['id'],replace(d,lines=tuple(reversed(d.lines))),expected_revision=2)
    assert result['received_quantity']==3


def test_dates_revision_and_atomicity(context):
    cat,repo,receipts,row=context
    for when,rev in [(date.today()+timedelta(days=1),1),(date.today()-timedelta(days=2),1),(date.today(),9)]:
        with pytest.raises(StorageError):receipts.receive(row['id'],when,expected_revision=rev)
    cat.connection.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON receipt_lines WHEN NEW.quantity=1 BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(StorageError):receipts.receive(row['id'],date.today(),expected_revision=1)
    assert receipts.current(row['id']) is None and repo.get(row['id'])['revision']==1


def test_migrate_schema10_without_inventing_receipts(tmp_path):
    path=tmp_path/'legacy';cat=CatalogRepository(path);repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    row=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,100),)),request_id='1')
    cat.connection.execute('DROP TABLE receipt_lines');cat.connection.execute('DROP TABLE purchase_receipts')
    for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): cat.connection.execute('DROP TABLE IF EXISTS '+table)
    cat.connection.execute('PRAGMA user_version=10');cat.connection.commit();cat.close()
    cat=CatalogRepository(path);repo=PurchasesRepository(cat.connection)
    assert repo.get(row['id'])['receipt'] is None
    assert repo.get(row['id'])['received_quantity']==0
    assert list(tmp_path.glob('*.backup-*'))
    cat.close()


def test_two_connections_receive_once(context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    cat,repo,receipts,row=context
    path=cat.connection.execute('PRAGMA database_list').fetchone()[2];barrier=Barrier(2)
    def receive():
        from pathlib import Path
        other=CatalogRepository(Path(path))
        try:
            barrier.wait(timeout=5)
            return PurchaseReceiptsRepository(other.connection).receive(row['id'],date.today(),expected_revision=1)['id']
        finally:other.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(receive);b=pool.submit(receive)
        assert a.result()==b.result()
    assert len(receipts.history(row['id']))==1


def test_reverse_allows_structural_edit_keeps_history(context):
    cat,repo,receipts,row=context
    r=receipts.receive(row['id'],date.today(),expected_revision=1)
    receipts.reverse(r['id'],'Error',expected_revision=2)
    draft=draft_from_record(repo.get(row['id']))
    repo.update(row['id'],replace(draft,lines=(draft.lines[0],)),expected_revision=3)
    history=receipts.history(row['id'])
    assert sum(line['quantity'] for line in history[0]['lines'])==3
    assert history[0]['lines'][1]['purchase_line_id'] is None
