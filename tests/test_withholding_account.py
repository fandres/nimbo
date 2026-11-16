from dataclasses import replace
from datetime import date
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
from mi_negocio.money_repository import MoneyRepository

def test_withholding_deposit_account_history_and_cancel(tmp_path):
    c=CatalogRepository(tmp_path/'db');s=SalesRepository(c.connection);settings=SettingsRepository(c.connection);m=MoneyRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')));method=settings.list_methods()[0]
    today=date.today();m.set_opening(1,today,0)
    d=SaleDraft(today,'F',(SaleLineInput(p.id,1,365300000),),method.id,1,customer_name='C',has_withholding=True)
    row=s.create(d,request_id='new',expected_method=method)
    assert row['deposit_cents']==356167500
    assert not m.movements()
    s.confirm_receipt(row['id'],ReceiptInput(today,1,0))
    moves=m.movements();ret=next(r for r in moves if r['account']=='Retenciones de renta')
    assert ret['delta']==9132500
    assert m.summary(today,today)['available']==356167500
    assert m.summary(today,today)['incoming']==356167500
    assert next(a for a in m.balances() if a['id']==ret['account_id'])['balance_cents']==9132500
    # Simulates the persisted policy on pre-migration rows.
    old=s.create(d,request_id='old',expected_method=method,receipt=ReceiptInput(today,1,0))
    c.connection.execute('UPDATE sales SET withholding_deducted=0 WHERE id=?',(old['id'],));c.connection.commit()
    assert s.get(old['id'])['deposit_cents']==365300000
    s.cancel(row['id'],'Prueba')
    assert not any(r['account']=='Retenciones de renta' for r in m.movements())
    assert m.summary(today,today)['available']==365300000
    c.close()


def test_policy_migration_preserves_old_sales_and_edits_are_atomic(tmp_path):
    import pytest
    from mi_negocio.storage import StorageError
    path=tmp_path/'db'
    c=CatalogRepository(path);s=SalesRepository(c.connection);settings=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')));method=settings.list_methods()[0]
    today=date.today()
    d=SaleDraft(today,'F',(SaleLineInput(p.id,1,100000),),method.id,1,customer_name='C',has_withholding=True)
    old=s.create(d,request_id='old',expected_method=method,receipt=ReceiptInput(today,1,0))
    c.connection.execute('ALTER TABLE sales DROP COLUMN withholding_deducted')
    c.connection.execute('PRAGMA user_version=21');c.connection.commit();c.close()
    c=CatalogRepository(path);s=SalesRepository(c.connection);m=MoneyRepository(c.connection)
    assert s.get(old['id'])['deposit_cents']==100000
    assert not any(r['account']=='Retenciones de renta' for r in m.movements())
    new=s.create(replace(d,has_withholding=False),request_id='new',expected_method=method,receipt=ReceiptInput(today,1,99000))
    with pytest.raises(StorageError):s.update_invoice(new['id'],'changed',True)
    assert s.get(new['id'])['invoice_ref']=='F' and not s.get(new['id'])['has_withholding']
    later=s.create(replace(d,has_withholding=False),request_id='later',expected_method=method)
    s.save_detail(later['id'],invoice_ref='OK',has_withholding=True,tracking_number='',receipt=ReceiptInput(today,1,100))
    assert s.get(later['id'])['deposit_cents']==97400
    assert sum(r['delta'] for r in m.movements() if r['account']=='Retenciones de renta')==2500
    s.update_invoice(later['id'],'OK',False)
    assert not any(r['account']=='Retenciones de renta' for r in m.movements())
    c.close()


def test_auxiliary_not_offered_for_payments(qtbot,tmp_path):
    from mi_negocio.ui.money_dialogs import MoneyEntryDialog
    c=CatalogRepository(tmp_path/'db');s=SalesRepository(c.connection);settings=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')));method=settings.list_methods()[0]
    s.create(SaleDraft(date.today(),'F',(SaleLineInput(p.id,1,100000),),method.id,1,customer_name='C',has_withholding=True),request_id='new',expected_method=method)
    d=MoneyEntryDialog(MoneyRepository(c.connection));qtbot.addWidget(d)
    from PySide6.QtWidgets import QComboBox
    for combo in d.findChildren(QComboBox):
        assert all(combo.itemText(i)!='Retenciones de renta' for i in range(combo.count()))
    c.close()
