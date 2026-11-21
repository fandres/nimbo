from datetime import date
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.money_repository import MoneyRepository
from mi_negocio.storage import StorageError


def test_opening_transfer_and_idempotency(tmp_path):
    cat=CatalogRepository(tmp_path/'db'); r=MoneyRepository(cat.connection); today=date.today()
    assert all(not a['configured'] for a in r.balances())
    r.set_opening(1,today,10000)
    r.set_opening(2,today,0)
    row=r.add('transfer',today,2500,'Mover',1,2,request_id='one')
    assert r.add('transfer',today,2500,'Mover',1,2,request_id='one')['id']==row['id']
    balances={a['id']:a['balance_cents'] for a in r.balances()}
    assert balances=={1:7500,2:2500}
    summary=r.summary(today,today)
    assert summary['incoming']==summary['outgoing']==summary['net']==0
    assert r.summary(today,today,1)['net']==-2500
    r.cancel(row['id'],'Error')
    assert r.balances()[0]['balance_cents']==10000
    with pytest.raises(StorageError):r.add('transfer',today,2500,'Mover',1,1,request_id='two')
    cat.close()


def test_opening_cutoff_and_revision(tmp_path):
    cat=CatalogRepository(tmp_path/'db');r=MoneyRepository(cat.connection)
    r.add('contribution',date(2020,1,1),500,'Aporte',None,1,request_id='old')
    r.set_opening(1,date(2020,1,2),1000)
    assert r.balances()[0]['balance_cents']==1000
    with pytest.raises(StorageError):r.set_opening(1,date(2020,1,2),2000)
    r.set_opening(1,date(2020,1,2),2000,expected_revision=1)
    assert r.balances()[0]['balance_cents']==2000
    cat.close()


def test_sources_no_double_count_card_expenses_and_interest(tmp_path):
    from mi_negocio.credit_cards import CreditCardsRepository
    from mi_negocio.expenses_repository import ExpensesRepository
    from mi_negocio.expenses import ExpenseDraft,ExpenseFilter
    from mi_negocio.settings_repository import SettingsRepository
    c=CatalogRepository(tmp_path/'db');r=MoneyRepository(c.connection);cards=CreditCardsRepository(c.connection);today=date.today()
    cards.set_enabled(True);card=cards.save_card('Visa');card_account=card['account_id']
    assert card_account not in [a.id for a in SettingsRepository(c.connection).list_accounts()]
    r.set_opening(2,today,100000);r.set_opening(card_account,today,0)
    e=ExpensesRepository(c.connection);category=e.categories()[0]['id']
    expense=e.save(ExpenseDraft('Compra con crédito',10000,today,category,today,card_account),request_id='exp')
    cards.charge(card['id'],today,200,50,request_id='interest')
    assert cards.debt(card['id'])['total_cents']==10250
    assert r.summary(today,today)['outgoing']==0
    payment=r.add('card_payment',today,5250,'Abono',2,card_account,request_id='payment',capital_cents=5000,interest_cents=200,fee_cents=50)
    assert cards.debt(card['id'])['total_cents']==5000
    assert r.summary(today,today)['outgoing']==5250
    assert e.summary(ExpenseFilter())['total_cents']==10250
    r.cancel(payment['id'],'Duplicado')
    assert cards.debt(card['id'])['total_cents']==10250
    e.cancel(expense['id'],expense['revision'],'Error')
    assert cards.debt(card['id'])['total_cents']==250
    c.close()


def test_sale_net_receipt_shipping_and_purchase_payment(tmp_path):
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput,ShippingPaymentInput
    from mi_negocio.sales_repository import SalesRepository
    from mi_negocio.purchases_repository import PurchasesRepository
    from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput
    c=CatalogRepository(tmp_path/'db');r=MoneyRepository(c.connection);today=date.today()
    product=c.create(validate_product(ProductInput('A','Máquina','product','100')))
    sales=SalesRepository(c.connection)
    sale=sales.create(SaleDraft(today,'F1',(SaleLineInput(product.id,1,10000),),1,1,True,500,700,customer_name='Cliente'),request_id='sale',expected_method=__import__('mi_negocio.settings_repository',fromlist=['SettingsRepository']).SettingsRepository(c.connection).list_methods()[0])
    assert not r.movements()
    sales.confirm_receipt(sale['id'],ReceiptInput(today,1,1000))
    sales.pay_shipping(sale['id'],ShippingPaymentInput(today,None,'credit_card'))
    summary=r.summary(today,today)
    assert summary['incoming']==9500 and summary['outgoing']==0 and summary['unassigned']==1
    sales.update_shipping_payment_details(sale['id'],1,'account')
    assert r.summary(today,today)['outgoing']==700
    purchase=PurchasesRepository(c.connection).create(PurchaseDraft(today,'Proveedor','',(PurchaseLineInput(product.id,1,5000),)),request_id='buy')
    assert r.summary(today,today)['outgoing']==700
    r.add('purchase_payment',today,5000,'Mercancía',1,request_id='paid',purchase_id=purchase['id'],purchase_category='merchandise')
    assert r.summary(today,today)['outgoing']==5700
    sales.cancel(sale['id'],'Error')
    assert r.summary(today,today)['incoming']==0 and r.summary(today,today)['outgoing']==5000
    c.close()


def test_migration_14_backup_and_rollback(tmp_path,monkeypatch):
    import sqlite3
    from mi_negocio import database
    path=tmp_path/'db';original=database.migrate_money
    monkeypatch.setattr(database,'migrate_money',lambda c:None)
    cat=CatalogRepository(path);cat.close()
    def fail(c):original(c);raise sqlite3.OperationalError('failure')
    monkeypatch.setattr(database,'migrate_money',fail)
    with pytest.raises(StorageError):CatalogRepository(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==13
        assert not c.execute("SELECT name FROM sqlite_master WHERE name='money_entries'").fetchone()
    monkeypatch.setattr(database,'migrate_money',original)
    cat=CatalogRepository(path)
    assert cat.connection.execute('PRAGMA user_version').fetchone()[0]==29
    assert not cat.connection.execute('PRAGMA foreign_key_check').fetchall()
    assert list(tmp_path.glob('*.backup-*'))
    cat.close()


def test_negative_money_format():
    from mi_negocio.ui.style import format_cop
    assert format_cop(-150)=='$ -1,50'


def test_backdated_card_payment_cannot_overpay_later_balance(tmp_path):
    from mi_negocio.credit_cards import CreditCardsRepository
    c=CatalogRepository(tmp_path/'db');r=MoneyRepository(c.connection);cards=CreditCardsRepository(c.connection)
    cards.set_enabled(True);card=cards.save_card('Visa');key=card['account_id']
    r.set_opening(key,date(2020,1,1),-10000)
    r.add('card_payment',date(2020,1,20),5000,'Abono',2,key,request_id='later')
    with pytest.raises(StorageError):r.add('card_payment',date(2020,1,10),6000,'Anterior',2,key,request_id='earlier')
    assert cards.debt(card['id'])['total_cents']==5000
    c.close()


def test_card_charge_is_not_a_second_pending_payable(tmp_path):
    from mi_negocio.credit_cards import CreditCardsRepository
    from mi_negocio.expenses_repository import ExpensesRepository
    from mi_negocio.expenses import ExpenseFilter
    c=CatalogRepository(tmp_path/'db');r=MoneyRepository(c.connection);cards=CreditCardsRepository(c.connection)
    cards.set_enabled(True);card=cards.save_card('Visa');key=card['account_id'];today=date.today()
    r.set_opening(key,today,0);cards.charge(card['id'],today,100,0,request_id='charge')
    r.add('card_payment',today,100,'Intereses',2,key,request_id='pay',capital_cents=0,interest_cents=100)
    assert cards.debt(card['id'])['total_cents']==0
    assert ExpensesRepository(c.connection).summary(ExpenseFilter())['pending_cents']==0
    c.close()


def test_disabled_card_control_blocks_payment_cancellation(tmp_path):
    from mi_negocio.credit_cards import CreditCardsRepository
    cat = CatalogRepository(tmp_path / 'db')
    r = MoneyRepository(cat.connection)
    cards = CreditCardsRepository(cat.connection)
    cards.set_enabled(True)
    card = cards.save_card('Visa')
    r.set_opening(card['account_id'], date.today(), -10000)
    payment = r.add('card_payment', date.today(), 1000, 'Abono', 2, card['account_id'], request_id='pay')
    cards.set_enabled(False)
    with pytest.raises(StorageError, match='Activa el control'):
        r.cancel(payment['id'], 'Error')
    assert cards.debt(card['id'])['total_cents'] == 9000
    cards.set_enabled(True)
    r.cancel(payment['id'], 'Error')
    assert cards.debt(card['id'])['total_cents'] == 10000
    cat.close()
