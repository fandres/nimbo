import sqlite3
from datetime import date
import pytest
from mi_negocio.credit_card_schema import migrate_credit_cards
from mi_negocio.credit_cards import CreditCardsRepository
from mi_negocio.catalog import ValidationError

@pytest.fixture
def repo():
    db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT,name_key TEXT UNIQUE,enabled INTEGER,kind TEXT,is_default INTEGER)')
    migrate_credit_cards(db)
    db.execute('CREATE TABLE account_openings(account_id INTEGER,opened_on TEXT)')
    db.commit()
    r = CreditCardsRepository(db); r.set_enabled(True)
    return r

def test_charge_idempotency_and_cancellation(repo):
    card = repo.save_card('Visa')
    a = repo.charge(card['id'], '2026-01-01', 100, 20, request_id='a')
    assert repo.charge(card['id'], '2026-01-01', 100, 20, request_id='a')['id'] == a['id']
    with pytest.raises(ValidationError): repo.charge(card['id'], '2026-01-01', 101, 20, request_id='a')
    repo.cancel_charge(a['id'], 'Duplicado')
    assert repo.connection.execute('SELECT cancelled_at FROM credit_card_charges').fetchone()[0]

def test_disabled_retains_history_and_revisions(repo):
    c = repo.save_card('Visa')
    repo.save_card('Visa nueva', card_id=c['id'], expected_revision=c['revision'])
    with pytest.raises(ValidationError): repo.save_card('Vieja', card_id=c['id'], expected_revision=c['revision'])
    repo.set_enabled(False)
    assert len(repo.list_cards()) == 1
    assert repo.events(c['id'])
    with pytest.raises(ValidationError): repo.charge(c['id'], '2026-01-01', 100, 0, request_id='b')

def test_reminder_clamps_and_no_cut(repo, monkeypatch):
    repo.save_card('Sin corte')
    c = repo.save_card('Visa', cut_day=31, remind_days=2)
    monkeypatch.setattr(repo, 'periods', lambda card_id: [])
    notices = repo.reminders(date(2026, 2, 26))
    assert any(n['card_id']==c['id'] and '28' in n['text'] for n in notices)
    assert not any(n['card_id']!=c['id'] for n in notices)

def test_invalid_input_does_not_create_card(repo):
    for kwargs in ({'rate':'NaN'}, {'cut_day':32}, {'remind_days':4}):
        with pytest.raises(ValidationError): repo.save_card('Bad', **kwargs)
    assert repo.list_cards() == []

@pytest.fixture
def integrated(tmp_path):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.money_repository import MoneyRepository
    catalog = CatalogRepository(tmp_path/'cards.db')
    cards = CreditCardsRepository(catalog.connection); cards.set_enabled(True)
    money = MoneyRepository(catalog.connection)
    card = cards.save_card('Tarjeta de prueba')
    money.set_opening(card['account_id'], date(2020,1,1), -10000)
    yield cards, money, card
    catalog.close()

def test_real_reconciliation_without_interest_and_retroactive_changes(integrated):
    cards, money, card = integrated
    p = cards.reconcile(card['id'], '2020-01-01','2020-01-31',10000, expected_revision=card['revision'])
    assert not p['provisional']
    assert not cards.debt(card['id'], '2020-01-31')['provisional']
    assert cards.debt(card['id'], '2020-02-01')['provisional']
    money.set_opening(card['account_id'],date(2020,1,1),-11000,expected_revision=1)
    assert cards.periods(card['id'])[0]['provisional']
    with pytest.raises(ValidationError): cards.reconcile(card['id'],'2020-01-01','2020-01-31',10000,expected_revision=cards.get(card['id'])['revision'])

def test_real_interest_payment_and_disabled_history(integrated):
    cards, money, card = integrated
    charge = cards.charge(card['id'], '2020-01-15', 100, 25, request_id='interest')
    money.set_opening(1,date(2020,1,1),20000)
    money.add('card_payment',date(2020,1,16),5000,'Pago',1,card['account_id'],request_id='payment')
    assert cards.debt(card['id'])['total_cents']==5125
    cards.reconcile(card['id'],'2020-01-01','2020-01-31',5125,expected_revision=card['revision'])
    cards.cancel_charge(charge['id'],'Corregir extracto')
    assert cards.periods(card['id'])[0]['provisional']
    cards.set_enabled(False)
    assert cards.debt(card['id'])['total_cents']==5000
    assert any(e['event_type']=='charge_cancelled' for e in cards.events(card['id']))
    assert cards.reminders()==[]

def test_edit_and_reconcile_require_revision(integrated):
    cards, money, card = integrated
    with pytest.raises(ValidationError): cards.save_card('Nuevo',card_id=card['id'])
    with pytest.raises(ValidationError): cards.reconcile(card['id'],'2020-01-01','2020-01-31',10000)

def test_no_reminder_for_period_before_opening(integrated):
    cards, money, card = integrated
    cards.save_card(card['name'],card_id=card['id'],cut_day=31,expected_revision=card['revision'])
    money.set_opening(card['account_id'],date(2020,2,1),-10000,expected_revision=1)
    assert cards.reminders(date(2020,2,10))==[]
    assert cards.reminders(date(2020,3,1))

def test_charge_history_survives_cancellation(repo):
    c = repo.save_card('Visa')
    charge = repo.charge(c['id'],'2020-01-01',30,0,request_id='history')
    repo.cancel_charge(charge['id'],'Error')
    assert repo.list_charges(c['id'])[0]['cancelled_at']

def test_source_amount_and_date_changes_invalidate_snapshot(integrated):
    cards, money, card = integrated
    charge = cards.charge(card['id'],'2020-01-15',100,0,request_id='retro')
    cards.reconcile(card['id'],'2020-01-01','2020-01-31',10100,expected_revision=card['revision'])
    with cards.connection:
        cards.connection.execute('UPDATE credit_card_charges SET interest_cents=200 WHERE id=?',(charge['id'],))
    assert cards.periods(card['id'])[0]['provisional']
    cards.reconcile(card['id'],'2020-01-01','2020-01-31',10200,expected_revision=cards.get(card['id'])['revision'])
    with cards.connection:
        cards.connection.execute("UPDATE credit_card_charges SET charged_on='2020-02-01' WHERE id=?",(charge['id'],))
    assert cards.periods(card['id'])[0]['provisional']

def test_rate_change_does_not_recalculate_real_interest(integrated):
    cards, money, card = integrated
    cards.charge(card['id'],'2020-01-15',100,0,request_id='real')
    cards.save_card(card['name'],rate='2.50',card_id=card['id'],expected_revision=card['revision'])
    assert cards.debt(card['id'])['total_cents']==10100
    assert cards.list_charges(card['id'])[0]['interest_cents']==100


def test_future_charges_rejected(repo):
    from datetime import timedelta
    card=repo.save_card('Visa')
    with pytest.raises(ValidationError):
        repo.charge(card['id'],date.today()+timedelta(days=1),100,0,request_id='future')
    assert repo.list_charges(card['id'])==[]
