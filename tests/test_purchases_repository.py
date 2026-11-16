from dataclasses import replace
from datetime import date
import json
import sqlite3
import pytest
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.storage import StorageError
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput, PurchaseCostInput, PurchasesFilter
from mi_negocio.purchases_repository import PurchasesRepository


@pytest.fixture
def setup(tmp_path):
    cat = CatalogRepository(tmp_path/'db.sqlite3')
    product = cat.create(validate_product(ProductInput('001', 'Máquina', 'product', '999')))
    repo = PurchasesRepository(cat.connection)
    draft = PurchaseDraft(date.today(), "O'Brian_%", 'REF', (PurchaseLineInput(product.id, 2, 10000),))
    yield cat, repo, draft
    cat.close()


def test_create_reopen_and_history(setup):
    cat, repo, draft = setup
    row = repo.create(draft, request_id='one')
    assert row['total_cents'] == 20000
    assert row['lines'][0]['code'] == '001'
    assert repo.create(draft, request_id='one')['id'] == row['id']
    with pytest.raises(StorageError): repo.create(replace(draft, reference='other'), request_id='one')
    edited = replace(draft, lines=(replace(draft.lines[0], line_id=row['lines'][0]['id']),),
                     costs=(PurchaseCostInput('taxes', '', 500),), costs_complete=True)
    updated = repo.update(row['id'], edited, expected_revision=1)
    assert updated['total_cents'] == 20500 and updated['revision'] == 2
    assert updated['revisions'][0]['snapshot']['total_cents'] == 20000
    with pytest.raises(StorageError): repo.update(row['id'], edited, expected_revision=1)
    assert repo.get(row['id'])['revision'] == 2
    # Requests remain idempotent even after a later correction.
    assert repo.create(draft, request_id='one')['id'] == row['id']


def test_filters_and_cancellation(setup):
    cat, repo, draft = setup
    row = repo.create(replace(draft, lines=draft.lines*2), request_id='one')
    assert len(repo.list_purchases(PurchasesFilter(query='001'))) == 1
    assert len(repo.list_purchases(PurchasesFilter(query="o'brian_%"))) == 1
    assert not repo.list_purchases(PurchasesFilter(query='_x%'))
    assert not repo.list_purchases(PurchasesFilter(costs_complete=True))
    assert repo.list_suppliers() == ["O'Brian_%"]
    with pytest.raises(StorageError): repo.cancel(row['id'], '', expected_revision=1)
    repo.cancel(row['id'], 'Duplicada', expected_revision=1)
    assert not repo.list_purchases(PurchasesFilter())
    assert repo.list_purchases(PurchasesFilter(cancelled=True))[0]['cancellation_reason'] == 'Duplicada'
    assert len(repo.get(row['id'])['lines']) == 2
    with pytest.raises(StorageError): repo.update(row['id'], draft, expected_revision=2)


def test_inactive_products_and_rollback(setup):
    cat, repo, draft = setup
    row = repo.create(draft, request_id='one')
    cat.set_active(draft.lines[0].product_id, False)
    with pytest.raises(StorageError): repo.create(draft, request_id='two')
    historical = replace(draft, lines=(replace(draft.lines[0], line_id=row['lines'][0]['id'], quantity=3),))
    assert repo.update(row['id'], historical, expected_revision=1)['quantity'] == 3
    with pytest.raises(StorageError): repo.update(row['id'], draft, expected_revision=2)
    cat.connection.execute("CREATE TRIGGER reject_cost BEFORE INSERT ON purchase_costs BEGIN SELECT RAISE(ABORT,'fail'); END")
    with pytest.raises(StorageError):
        repo.update(row['id'], replace(historical, costs=(PurchaseCostInput('taxes','',100),)), expected_revision=2)
    assert repo.get(row['id'])['revision'] == 2
    assert repo.get(row['id'])['costs'] == []


def test_service_rejected_and_snapshot_kept(setup):
    cat, repo, draft = setup
    row = repo.create(draft, request_id='one')
    cat.connection.execute("UPDATE products SET name='Nuevo nombre' WHERE code='001'")
    cat.connection.commit()
    assert repo.get(row['id'])['lines'][0]['name'] == 'Máquina'
    product = cat.create(validate_product(ProductInput('S', 'Servicio', 'service', '100')))
    with pytest.raises(StorageError):
        repo.create(replace(draft, lines=(PurchaseLineInput(product.id,1,100),)), request_id='bad')


def test_v8_migration_backup_and_reopen(tmp_path):
    path = tmp_path/'old.sqlite3'
    cat = CatalogRepository(path)
    cat.connection.execute("UPDATE accounts SET name='Mi banco' WHERE id=2")
    for table in ('receipt_lines','purchase_receipts','purchase_revisions','purchase_costs','purchase_lines','purchases'):
        cat.connection.execute('DROP TABLE '+table)
    for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): cat.connection.execute('DROP TABLE IF EXISTS '+table)
    cat.connection.execute('PRAGMA user_version=8')
    cat.connection.commit(); cat.close()
    cat = CatalogRepository(path)
    assert cat.connection.execute('PRAGMA user_version').fetchone()[0] ==25
    assert cat.connection.execute('SELECT name FROM accounts WHERE id=2').fetchone()[0] == 'Mi banco'
    cat.close()
    backups = list(tmp_path.glob('*.backup-*'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 8
    cat = CatalogRepository(path); cat.close()
    assert len(list(tmp_path.glob('*.backup-*'))) == 1


def test_reopen_preserves_each_rate_and_source_amount(tmp_path):
    from decimal import Decimal
    from datetime import timedelta
    path=tmp_path/'persist.sqlite3'
    cat=CatalogRepository(path)
    product=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    repo=PurchasesRepository(cat.connection)
    today=date.today(); earlier=today-timedelta(days=2)
    draft=PurchaseDraft(earlier,'Proveedor','',(
        PurchaseLineInput(product.id,2,30000,'USD',Decimal('4200'),earlier),),(
        PurchaseCostInput('international_shipping','',5000,'USD',Decimal('4250'),today),
        PurchaseCostInput('taxes','',40000000,'COP',Decimal('4300'),today)))
    key=repo.create(draft,request_id='persist')['id']; cat.close()
    cat=CatalogRepository(path); result=PurchasesRepository(cat.connection).get(key)
    assert result['total_cents']==313250000
    assert result['lines'][0]['exchange_rate']=='4200'
    assert [c['exchange_rate'] for c in result['costs']]==['4250','4300']
    assert result['lines'][0]['converted_on']==earlier.isoformat()
    assert result['costs'][1]['amount_cents']==40000000
    cat.close()


def test_purchase_migration_failure_rolls_back(tmp_path,monkeypatch):
    from mi_negocio import database
    path=tmp_path/'old.sqlite3'; cat=CatalogRepository(path)
    for table in ('receipt_lines','purchase_receipts','purchase_revisions','purchase_costs','purchase_lines','purchases'):
        cat.connection.execute('DROP TABLE '+table)
    for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): cat.connection.execute('DROP TABLE IF EXISTS '+table)
    cat.connection.execute('PRAGMA user_version=8'); cat.connection.commit(); cat.close()
    original=database.migrate_purchases
    def fail(connection):
        original(connection)
        raise sqlite3.OperationalError('injected migration failure')
    monkeypatch.setattr(database,'migrate_purchases',fail)
    with pytest.raises(StorageError): CatalogRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==8
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='purchases'").fetchall()
        assert db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]==2


def test_allocations_and_states_persist(setup):
    cat, repo, draft = setup
    d=replace(draft,lines=(replace(draft.lines[0],shipping_allocated_cents=500),),
              costs=(PurchaseCostInput('international_shipping','',500),),costs_complete=True,
              cost_states=dict(international_shipping='recorded',importation='not_applicable',taxes='not_applicable',other='not_applicable'))
    row=repo.create(d,request_id='allocated')
    assert row['lines'][0]['shipping_allocated_cents']==500
    assert row['cost_states']==d.cost_states
    assert repo.list_purchases(PurchasesFilter(progress='complete'))[0]['id']==row['id']
    assert not repo.list_purchases(PurchasesFilter(progress='nationalization_pending'))


def test_schema9_migration_and_original_request(tmp_path):
    from mi_negocio.purchase_allocation import ALLOCATION_FIELDS
    path=tmp_path/'legacy.sqlite3'; cat=CatalogRepository(path)
    product=cat.create(validate_product(ProductInput('001','Histórica','product','10')))
    repo=PurchasesRepository(cat.connection)
    draft=PurchaseDraft(date.today(),'Proveedor','', (PurchaseLineInput(product.id,1,10000),),
                        (PurchaseCostInput('taxes','',500),))
    row=repo.create(draft,request_id='old')
    payload=json.loads(cat.connection.execute('SELECT request_payload FROM purchases').fetchone()[0])
    payload.pop('cost_states')
    for line in payload['lines']:
        for field in ALLOCATION_FIELDS.values(): line.pop(field)
    cat.connection.execute('UPDATE purchases SET request_payload=?',(json.dumps(payload),))
    for field in ALLOCATION_FIELDS.values(): cat.connection.execute('ALTER TABLE purchase_lines DROP COLUMN '+field)
    cat.connection.execute('ALTER TABLE purchases DROP COLUMN cost_states_json')
    cat.connection.execute('DROP TABLE receipt_lines');cat.connection.execute('DROP TABLE purchase_receipts')
    for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): cat.connection.execute('DROP TABLE IF EXISTS '+table)
    cat.connection.execute('PRAGMA user_version=9'); cat.connection.commit(); cat.close()
    cat=CatalogRepository(path); repo=PurchasesRepository(cat.connection)
    migrated=repo.get(row['id'])
    assert migrated['total_cents']==10500 and migrated['cost_states'] is None
    assert migrated['lines'][0]['taxes_allocated_cents']==0
    assert repo.create(draft,request_id='old')['id']==row['id']
    assert list(tmp_path.glob('*.backup-*'))
    assert not repo.list_purchases(PurchasesFilter(progress='nationalization_pending'))
    assert repo.list_purchases(PurchasesFilter(progress='costs_pending'))
    cat.close()
