import sqlite3
from dataclasses import replace
from decimal import Decimal
import pytest
from mi_negocio.repository import CatalogRepository, StorageError
from mi_negocio.settings_repository import SettingsRepository


def test_seed_and_persist(tmp_path):
    path=tmp_path/'db.sqlite3'
    repo=CatalogRepository(path)
    settings=SettingsRepository(repo.connection)
    methods=settings.list_methods()
    assert [(m.name,str(m.rate_percent),m.fixed_cents) for m in methods]==[('Efectivo','0',0),('Transferencia','0',0),('Tarjeta','3.59',90000),('Addi','7.735',0)]
    settings.save_method(replace(methods[2],rate_percent=Decimal('2.125')))
    repo.close()
    repo=CatalogRepository(path)
    assert SettingsRepository(repo.connection).list_methods()[2].rate_percent==Decimal('2.125')
    repo.close()


def old_db(path):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE products(id INTEGER PRIMARY KEY,code TEXT,name TEXT,kind TEXT,price_cop_cents INTEGER,active INTEGER,created_at TEXT,updated_at TEXT,brand_id INTEGER,subtype_id INTEGER)')
        db.execute('CREATE TABLE catalog_options(id INTEGER PRIMARY KEY,group_key TEXT,name TEXT,name_key TEXT)')
        db.execute("INSERT INTO products VALUES(1,'001','Original','product',100,1,'old','old',NULL,NULL)")
        for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): db.execute('DROP TABLE IF EXISTS '+table)
        db.execute('PRAGMA user_version=2')


def test_backup_migration(tmp_path):
    path=tmp_path/'db.sqlite3'; old_db(path)
    repo=CatalogRepository(path)
    assert repo.list_products()[0].code=='001'
    assert repo.connection.execute('PRAGMA user_version').fetchone()[0]==25
    repo.close()
    backup=next(tmp_path.glob('*.backup-*'))
    with sqlite3.connect(backup) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==2
        assert db.execute('SELECT code FROM products').fetchone()[0]=='001'


def test_backup_failure_preserves_original(tmp_path,monkeypatch):
    from mi_negocio import database
    path=tmp_path/'db.sqlite3'; old_db(path)
    def fail(*a): raise OSError('full')
    monkeypatch.setattr(database,'backup_database',fail)
    with pytest.raises(StorageError): CatalogRepository(path)
    with sqlite3.connect(path) as db: assert db.execute('PRAGMA user_version').fetchone()[0]==2


def test_migration_failure_rolls_back(tmp_path,monkeypatch):
    from mi_negocio import database
    path=tmp_path/'db';old_db(path)
    original=database.migrate_sales
    def fail(connection):
        original(connection)
        raise sqlite3.OperationalError('injected')
    monkeypatch.setattr(database,'migrate_sales',fail)
    with pytest.raises(StorageError):CatalogRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==2
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='sales'").fetchall()


def test_accounts_rename_disable_and_duplicates(tmp_path):
    from mi_negocio.sales import Account
    repo=CatalogRepository(tmp_path/'db');settings=SettingsRepository(repo.connection)
    account=settings.save_account(Account(0,'Banco'))
    settings.save_account(replace(account,name='Banco personal',enabled=False))
    assert account.id not in [a.id for a in settings.list_accounts()]
    assert settings.list_accounts(True)[-1].name=='Banco personal'
    with pytest.raises(StorageError):settings.save_account(Account(0,' EFECTIVO '))
    repo.close()


def test_account_defaults_and_method_policy_survive_rename(tmp_path):
    from mi_negocio.sales import Account
    repo=CatalogRepository(tmp_path/'db');settings=SettingsRepository(repo.connection)
    cash=settings.list_methods()[0]
    settings.save_method(replace(cash,name='Caja del taller'))
    assert settings.list_methods()[0].account_kind=='cash'
    extra=settings.save_account(Account(0,'Caja secundaria',True,'cash',True))
    assert [a.id for a in settings.list_accounts() if a.is_default and a.kind=='cash']==[extra.id]
    repo.close()


def test_migration_v3_preserves_accounts_and_tariffs(tmp_path):
    from mi_negocio.database import migrate_catalog,migrate_sales
    path=tmp_path/'old3.sqlite3'
    with sqlite3.connect(path) as db:
        migrate_catalog(db,0);migrate_sales(db)
        db.execute("UPDATE payment_methods SET rate_percent='4.125' WHERE id=3")
        db.execute("INSERT INTO accounts(name,name_key,enabled) VALUES('Nequi','nequi',1)")
    repo=CatalogRepository(path);settings=SettingsRepository(repo.connection)
    assert settings.list_methods()[2].rate_percent==Decimal('4.125')
    assert settings.list_accounts()[-1].name=='Nequi'
    assert settings.list_accounts()[-1].kind=='bank'
    assert settings.list_accounts()[0].is_default
    repo.close()


def test_v4_migration_keeps_custom_accounts(tmp_path):
    path=tmp_path/'v4.sqlite3';repo=CatalogRepository(path);repo.close()
    with sqlite3.connect(path) as db:
        for name in ('customer_name','carrier_id','carrier_name','destination_city','has_withholding','tracking_number'):
            db.execute('ALTER TABLE sales DROP COLUMN '+name)
        db.execute('DROP TABLE carriers')
        db.execute("UPDATE accounts SET name='Mi caja',name_key='mi caja' WHERE id=1")
        db.execute('ALTER TABLE sales DROP COLUMN customer_identification')
        db.execute('ALTER TABLE sales DROP COLUMN customer_email')
        db.execute('ALTER TABLE shipping_payments DROP COLUMN payment_kind')
        db.execute('ALTER TABLE sales DROP COLUMN cancelled_at')
        db.execute('ALTER TABLE sales DROP COLUMN cancellation_reason')
        for table in ('receipt_lines','purchase_receipts','purchase_revisions','purchase_costs','purchase_lines','purchases'):
            db.execute('DROP TABLE '+table)
        for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): db.execute('DROP TABLE IF EXISTS '+table)
        db.execute('PRAGMA user_version=4')
    repo=CatalogRepository(path)
    assert repo.connection.execute('PRAGMA user_version').fetchone()[0]==25
    assert SettingsRepository(repo.connection).list_accounts()[0].name=='Mi caja'
    assert len(SettingsRepository(repo.connection).list_carriers())==2
    repo.close()


def test_v5_migration_adds_optional_tracking_and_keeps_settings(tmp_path):
    path=tmp_path/'v5.sqlite3';repo=CatalogRepository(path);repo.close()
    with sqlite3.connect(path) as db:
        db.execute('ALTER TABLE sales DROP COLUMN tracking_number')
        db.execute("UPDATE carriers SET name='Mi transportadora' WHERE id=1")
        db.execute('ALTER TABLE sales DROP COLUMN customer_identification')
        db.execute('ALTER TABLE sales DROP COLUMN customer_email')
        db.execute('ALTER TABLE shipping_payments DROP COLUMN payment_kind')
        db.execute('ALTER TABLE sales DROP COLUMN cancelled_at')
        db.execute('ALTER TABLE sales DROP COLUMN cancellation_reason')
        for table in ('receipt_lines','purchase_receipts','purchase_revisions','purchase_costs','purchase_lines','purchases'):
            db.execute('DROP TABLE '+table)
        for table in ('credit_card_events','credit_card_periods','credit_card_charges','credit_cards','credit_card_settings','money_events','money_entries','account_openings','loan_events','loan_payments','loans','expense_revisions','expenses','expense_categories','inventory_movements','inventory_baseline_receipts','inventory_state'): db.execute('DROP TABLE IF EXISTS '+table)
        db.execute('PRAGMA user_version=5')
    repo=CatalogRepository(path)
    assert repo.connection.execute('PRAGMA user_version').fetchone()[0]==25
    assert 'tracking_number' in [row[1] for row in repo.connection.execute('PRAGMA table_info(sales)')]
    assert repo.connection.execute('SELECT name FROM carriers WHERE id=1').fetchone()[0]=='Mi transportadora'
    repo.close()
    backup=next(tmp_path.glob('*.backup-*'))
    with sqlite3.connect(backup) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==5
