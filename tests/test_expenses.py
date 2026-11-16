from datetime import date, timedelta
from dataclasses import replace
import sqlite3
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.storage import StorageError
from mi_negocio.catalog import ValidationError, ProductInput, validate_product
from mi_negocio.expenses import ExpenseDraft, ExpenseFilter, comparison_period
from mi_negocio.expenses_repository import ExpensesRepository
from mi_negocio.loans_repository import LoansRepository


@pytest.fixture
def repos(tmp_path):
    catalog=CatalogRepository(tmp_path/'test.db')
    yield catalog,ExpensesRepository(catalog.connection),LoansRepository(catalog.connection)
    catalog.close()


def draft(repo, **changes):
    return replace(ExpenseDraft('Publicidad',100000,date.today(),repo.categories()[0]['id']),**changes)


@pytest.mark.parametrize('start,end,monthly,expected',[
    (date(2026,10,1),date(2026,10,23),True,(date(2026,9,1),date(2026,9,23))),
    (date(2024,3,1),date(2024,3,31),True,(date(2024,2,1),date(2024,2,29))),
    (date(2025,2,1),date(2025,2,28),True,(date(2025,1,1),date(2025,1,31))),
    (date(2026,1,1),date(2026,1,15),True,(date(2025,12,1),date(2025,12,15))),
    (date(2026,3,20),date(2026,4,2),False,(date(2026,3,6),date(2026,3,19))),
])
def test_comparison_period(start,end,monthly,expected):
    assert comparison_period(start,end,monthly)==expected


def test_expense_lifecycle_history_and_stale_write(repos):
    _,r,_=repos; d=draft(r)
    row=r.save(d,request_id='once')
    assert r.save(d,request_id='once')['id']==row['id']
    with pytest.raises(StorageError):r.save(replace(d,amount_cents=200000),request_id='once')
    paid=replace(d,paid_on=date.today(),account_id=1)
    updated=r.save(paid,expense_id=row['id'],expected_revision=row['revision'])
    with pytest.raises(StorageError):r.save(d,expense_id=row['id'],expected_revision=row['revision'])
    assert r.summary(ExpenseFilter())['paid_cents']==100000
    r.cancel(row['id'],updated['revision'],'Registro de prueba')
    assert r.summary(ExpenseFilter())['total_cents']==0
    assert len(r.history(row['id']))==3
    assert r.list_movements(ExpenseFilter(cancelled=None))[0]['cancelled']


def test_validation_and_categories(repos):
    c,r,_=repos
    for d in [draft(r,concept=' '),draft(r,amount_cents=0),draft(r,paid_on=date.today()),
              draft(r,spent_on=date.today()+timedelta(days=1)),draft(r,account_id=1),
              draft(r,paid_on=date.today()-timedelta(days=1),account_id=1)]:
        with pytest.raises((StorageError,ValidationError)):r.save(d,request_id='invalid')
    category=r.save_category(None,'Publicidad',True)
    row=r.save(draft(r,category_id=category),request_id='ok')
    r.save_category(category,'Marketing digital',False)
    assert r.list_movements(ExpenseFilter())[0]['category']=='Marketing digital'
    r.save(replace(draft(r,category_id=category),note='Dato adicional'),expense_id=row['id'],expected_revision=1)
    with pytest.raises(StorageError):r.save(draft(r,category_id=category),request_id='disabled')
    with pytest.raises(StorageError):r.save_category(None,' marketing DIGITAL ',True)
    c.connection.execute('UPDATE accounts SET enabled=0 WHERE id=1');c.connection.commit()
    with pytest.raises(StorageError):r.save(draft(r,paid_on=date.today(),account_id=1),request_id='bad-account')


def test_filters_totals_previous_zero_and_last_four(repos):
    _,r,_=repos
    for i in range(6):r.save(draft(r,concept='Servicio '+str(i),amount_cents=(i+1)*100,spent_on=date.today()-timedelta(days=i)),request_id=str(i))
    result=r.summary(ExpenseFilter())
    assert result['total_cents']==2100
    assert len(result['recent'])==4
    assert result['recent'][0]['concept']=='Servicio 0'
    assert sum(item['amount_cents'] for item in result['categories'])==2100
    assert r.summary(ExpenseFilter(query='Servicio 3'))['total_cents']==400
    assert r.summary(ExpenseFilter(account_id=1))['total_cents']==0


def test_loan_capital_interest_and_reversal(repos):
    _,r,loans=repos
    loan=loans.save_loan('Banco',date.today(),1000000,request_id='loan')
    payment=loans.pay(loan['id'],date.today(),1,300000,50000,request_id='pay')
    assert loans.pay(loan['id'],date.today(),1,300000,50000,request_id='pay')['id']==payment['id']
    assert loans.list_loans()[0]['balance_cents']==700000
    assert r.summary(ExpenseFilter())['total_cents']==50000
    assert r.summary(ExpenseFilter())['paid_cents']==50000
    assert r.summary(ExpenseFilter())['loan_capital_cents']==300000
    with pytest.raises(StorageError):loans.pay(loan['id'],date.today(),1,800000,0,request_id='too-much')
    with pytest.raises(StorageError):loans.save_loan('Other',date.today(),1000,loan_id=loan['id'],expected_revision=1)
    loans.cancel_payment(payment['id'],'Error de registro')
    assert loans.list_loans()[0]['balance_cents']==1000000
    assert r.summary(ExpenseFilter())['total_cents']==0
    assert r.summary(ExpenseFilter())['loan_capital_cents']==0
    with pytest.raises(StorageError):loans.cancel_payment(payment['id'],'Otra vez')


def test_sale_costs_projected_once_and_cancelled(repos):
    from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput,ShippingPaymentInput
    from mi_negocio.sales_repository import SalesRepository
    from mi_negocio.settings_repository import SettingsRepository
    catalog,r,_=repos; sales=SalesRepository(catalog.connection)
    product=catalog.create(validate_product(ProductInput('01','Servicio','service','100000')))
    method=SettingsRepository(catalog.connection).list_methods()[2]
    sale=sales.create(SaleDraft(date.today(),'F1',(SaleLineInput(product.id,1,10000000),),method.id,2,True,0,200000,'Cliente'),request_id='sale',expected_method=method)
    rows=r.list_movements(ExpenseFilter())
    assert len(rows)==2 and all(row['origin']=='sale' for row in rows)
    assert any(row['estimated'] for row in rows)
    sales.confirm_receipt(sale['id'],ReceiptInput(date.today(),2,400000))
    sales.pay_shipping(sale['id'],ShippingPaymentInput(date.today(),None,'credit_card'))
    rows=r.list_movements(ExpenseFilter())
    assert len(rows)==2 and sum(row['amount_cents'] for row in rows)==600000
    assert all(row['paid'] for row in rows)
    assert r.summary(ExpenseFilter(account_id=2))['total_cents']==400000
    sales.cancel(sale['id'],'Prueba')
    assert r.summary(ExpenseFilter())['total_cents']==0


def test_schema_12_backup_and_inventory_preserved(tmp_path):
    from mi_negocio import database
    path=tmp_path/'v12.db'
    # A genuine schema 12, rather than downgrading a new schema with extra tables.
    original=database.migrate_expenses; original_money=database.migrate_money
    database.migrate_money=lambda connection:None
    database.migrate_expenses=lambda connection:None
    try:
        c=CatalogRepository(path);c.connection.execute("UPDATE inventory_state SET revision=17");c.connection.commit();c.close()
    finally:database.migrate_expenses=original;database.migrate_money=original_money
    c=CatalogRepository(path)
    assert c.connection.execute('PRAGMA user_version').fetchone()[0]==25
    assert c.connection.execute('SELECT revision FROM inventory_state').fetchone()[0]==17
    assert c.connection.execute('PRAGMA foreign_key_check').fetchall()==[]
    c.close()
    with sqlite3.connect(next(tmp_path.glob('*.backup-*'))) as backup:
        assert backup.execute('PRAGMA user_version').fetchone()[0]==12


def test_same_day_recent_uses_numeric_order(repos):
    _,r,_=repos
    for i in range(12):r.save(draft(r,concept=f'Gasto {i}'),request_id=f'order{i}')
    assert [row['concept'] for row in r.summary()['recent']]==['Gasto 11','Gasto 10','Gasto 9','Gasto 8']


def test_atomic_audit_failure_does_not_save_expense(repos,monkeypatch):
    _,r,_=repos
    def fail(key):raise StorageError('Fallo de prueba al guardar historial')
    monkeypatch.setattr(r,'_audit',fail)
    with pytest.raises(StorageError):r.save(draft(r),request_id='rollback')
    assert r.list_movements()==[]


def test_two_connections_stale_expense_and_loan_balance(tmp_path):
    path=tmp_path/'two.db';a=CatalogRepository(path);b=CatalogRepository(path)
    try:
        first=ExpensesRepository(a.connection);second=ExpensesRepository(b.connection)
        row=first.save(draft(first),request_id='expense')
        second.save(draft(second,concept='Changed'),expense_id=row['id'],expected_revision=1)
        with pytest.raises(StorageError):first.cancel(row['id'],1,'Old view')
        loan_a=LoansRepository(a.connection);loan_b=LoansRepository(b.connection)
        loan=loan_a.save_loan('Banco',date.today(),100000,request_id='loan')
        loan_a.pay(loan['id'],date.today(),1,60000,1000,request_id='first')
        with pytest.raises(StorageError):loan_b.pay(loan['id'],date.today(),1,60000,1000,request_id='second')
        assert loan_b.list_loans()[0]['balance_cents']==40000
    finally:a.close();b.close()


def test_migration_13_failure_is_atomic(tmp_path,monkeypatch):
    from mi_negocio import database
    path=tmp_path/'v12';original=database.migrate_expenses
    monkeypatch.setattr(database,'migrate_money',lambda c:None)
    monkeypatch.setattr(database,'migrate_expenses',lambda c:None)
    c=CatalogRepository(path);c.close()
    def fail(c):
        original(c)
        raise sqlite3.OperationalError('Injected failure')
    monkeypatch.setattr(database,'migrate_expenses',fail)
    with pytest.raises(StorageError):CatalogRepository(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==12
        assert c.execute("SELECT name FROM sqlite_master WHERE name='expenses'").fetchall()==[]
        assert c.execute('SELECT initialized FROM inventory_state').fetchone()[0]==0


def test_payment_cannot_predate_loan_and_disabled_account(repos):
    cat,_,loans=repos
    loan=loans.save_loan('Banco',date.today(),100000,request_id='loan')
    with pytest.raises((StorageError,ValidationError)):loans.pay(loan['id'],date.today()-timedelta(days=1),1,1000,100,request_id='old')
    cat.connection.execute('UPDATE accounts SET enabled=0 WHERE id=1');cat.connection.commit()
    with pytest.raises(StorageError):loans.pay(loan['id'],date.today(),1,1000,100,request_id='disabled')
    assert loans.payments(loan['id'])==[]


def test_concept_suggestions_latest_category_unique_and_active(repos):
    _,r,_=repos
    categories=r.categories();first=categories[0]['id'];last=categories[1]['id']
    r.save(draft(r,concept='Facebook publicidad',category_id=first),request_id='concept1')
    latest=r.save(draft(r,concept='FACEBOOK publicidad',category_id=last),request_id='concept2')
    r.save(draft(r,concept='Otra cosa'),request_id='concept3')
    assert r.concept_suggestions('fa')==[]
    rows=r.concept_suggestions('face')
    assert len(rows)==1 and rows[0]['category_id']==last
    assert r.concept_suggestions('public')[0]['concept']=='FACEBOOK publicidad'
    r.cancel(latest['id'],latest['revision'],'Prueba')
    assert r.concept_suggestions('face')[0]['category_id']==first
    r.save_category(first,'Insumos',False)
    assert r.concept_suggestions('face')==[]
