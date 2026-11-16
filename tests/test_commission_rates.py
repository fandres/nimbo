from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import pytest
from mi_negocio.catalog import ProductInput, validate_product, ValidationError
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.sales import PaymentMethod, SaleDraft, SaleLineInput, ReceiptInput
from mi_negocio.commissions import CommissionTier, effective_fee
from mi_negocio.expenses import ExpenseFilter
from mi_negocio.expenses_repository import ExpensesRepository
from mi_negocio.storage import StorageError


def test_thresholds():
    m=PaymentMethod(1,'Plataforma','',Decimal('5'),90000,tiers=(CommissionTier(10000000,Decimal('3'),50000),))
    assert effective_fee(m,9999999)==(Decimal('5'),90000)
    assert effective_fee(m,10000000)==(Decimal('3'),50000)
    for tiers in [(CommissionTier(0,Decimal('2'),0),),(CommissionTier(100,Decimal('NaN'),0),),(CommissionTier(100,Decimal('2'),0),)*2]:
        with pytest.raises(ValidationError):effective_fee(replace(m,tiers=tiers),200)


def test_snapshots_overrides_and_expense_platform(tmp_path):
    c=CatalogRepository(tmp_path/'db');s=SettingsRepository(c.connection);r=SalesRepository(c.connection);e=ExpensesRepository(c.connection)
    p=c.create(validate_product(ProductInput('X','Máquina','product','1000')))
    m=s.save_method(PaymentMethod(0,'Siste Crédito','Siste Crédito',Decimal('5'),0,tiers=(CommissionTier(100000,Decimal('3'),100),)))
    assert s.list_methods()[-1]==m
    today=date.today();sold=today-timedelta(days=5)
    d=SaleDraft(sold,'F1',(SaleLineInput(p.id,1,90000),),m.id,2,True,10000,10000,customer_name='Cliente')
    a=r.create(d,request_id='auto',expected_method=m,receipt=ReceiptInput(today,2,3200))
    assert a['rate_percent']=='3' and a['commission_cents']==3100
    b=r.create(replace(d,commission_override=(Decimal('2'),0)),request_id='manual',expected_method=m)
    assert b['commission_cents']==2000
    f=ExpenseFilter(start=today,end=today,method_id=m.id,date_basis='paid')
    assert e.summary(f)['paid_cents']==3200
    assert e.summary(replace(f,date_basis='spent'))['total_cents']==0
    assert e.summary(ExpenseFilter(method_id=m.id))['total_cents']==5200
    s.save_method(replace(m,name='Nuevo nombre',enabled=False,tiers=()))
    assert e.commission_methods()==[(m.id,'Siste Crédito')]
    assert e.list_movements(f)[0]['platform']=='Siste Crédito'
    assert r.get(a['id'])['commission_cents']==3100
    assert r.create(d,request_id='auto',expected_method=m,receipt=ReceiptInput(today,2,3200))['id']==a['id']
    r.cancel(a['id']);assert e.summary(f)['paid_cents']==0
    c.close()


def test_concurrent_tier_edit_rejected(tmp_path):
    c=CatalogRepository(tmp_path/'db');s=SettingsRepository(c.connection);r=SalesRepository(c.connection)
    p=c.create(validate_product(ProductInput('X','X','product','1000')));m=s.list_methods()[0]
    s.save_method(replace(m,tiers=(CommissionTier(100,Decimal('1'),0),)))
    with pytest.raises(StorageError):r.create(SaleDraft(date.today(),'F',(SaleLineInput(p.id,1,100000),),m.id,1,customer_name='C'),request_id='stale',expected_method=m)
    c.close()


def test_expense_platform_filters_ui(qtbot,tmp_path):
    from mi_negocio.ui.expenses_page import ExpensesPage
    from mi_negocio.ui.settings_page import SettingsEditor
    from mi_negocio.ui.sale_dialog import SaleDialog
    c=CatalogRepository(tmp_path/'db');s=SettingsRepository(c.connection);r=SalesRepository(c.connection)
    p=c.create(validate_product(ProductInput('X','Máquina','product','1000')))
    m=s.save_method(PaymentMethod(0,'Siste Crédito','Siste Crédito',Decimal('5'),0,tiers=(CommissionTier(100000,Decimal('3'),0),)))
    dialog=SaleDialog(c,s,r);qtbot.addWidget(dialog)
    dialog.choose_method(m)
    dialog.lines=[SaleLineInput(p.id,1,100000)]
    dialog.recalculate()
    assert dialog.fee_rate.text()=='3'
    assert not dialog.adjust_fee.isChecked()
    dialog.adjust_fee.setChecked(True);dialog.fee_rate.setText('2');dialog.recalculate()
    assert dialog.totals().commission_cents==2000
    dialog.adjust_fee.setChecked(False)
    assert dialog.totals().commission_cents==3000
    r.create(SaleDraft(date.today(),'F',(SaleLineInput(p.id,1,100000),),m.id,2,customer_name='C'),request_id='x',expected_method=m,receipt=ReceiptInput(date.today(),2,2900))
    page=ExpensesPage(ExpensesRepository(c.connection),s);qtbot.addWidget(page)
    page.platform.setCurrentIndex(page.platform.findData(m.id))
    page.date_basis.setCurrentIndex(page.date_basis.findData('paid'))
    assert page.filtered_summary['paid_cents']==2900
    assert page.summary_data['paid_cents']==2900
    assert 'Siste Crédito' in page.table.item(0,1).text()
    editor=SettingsEditor(s);qtbot.addWidget(editor)
    editor.table.selectRow(len(editor.rows)-1)
    assert editor.tiers_button.text()=='Tarifas por monto · 1'
    c.close()


def test_fee_selected_before_product_and_reload(qtbot,tmp_path):
    from mi_negocio.ui.sale_dialog import SaleDialog
    c=CatalogRepository(tmp_path/'db');s=SettingsRepository(c.connection)
    d=SaleDialog(c,s,SalesRepository(c.connection));qtbot.addWidget(d)
    d.choose_method(s.list_methods()[2]);d.adjust_fee.setChecked(True)
    assert d.fee_rate.text()=='3.59'
    d.fee_rate.setText('1');d.reload_options()
    assert not d.adjust_fee.isChecked()
    c.close()


def test_v19_migration_preserves_tariffs_and_sales(tmp_path):
    c=CatalogRepository(tmp_path/'db');s=SettingsRepository(c.connection);r=SalesRepository(c.connection)
    m=s.list_methods()[2];p=c.create(validate_product(ProductInput('P','Product','product','1000')))
    a=r.create(SaleDraft(date.today(),'F',(SaleLineInput(p.id,1,1000000),),m.id,2,customer_name='C'),request_id='old',expected_method=m)
    c.connection.execute('ALTER TABLE payment_methods DROP COLUMN tiers_json');c.connection.execute('PRAGMA user_version=19');c.connection.commit();c.close()
    c=CatalogRepository(tmp_path/'db')
    assert SettingsRepository(c.connection).list_methods()[2]==m
    assert SalesRepository(c.connection).get(a['id'])['commission_cents']==a['commission_cents']
    c.close()


def test_tier_editor_validates_and_sorts(qtbot):
    from mi_negocio.ui.commission_tiers import CommissionTiersDialog
    d=CommissionTiersDialog(());qtbot.addWidget(d)
    d.add_row(CommissionTier(200000,Decimal('2.345678'),900));d.add_row(CommissionTier(100000,Decimal('3'),0))
    d.persist();assert d.result()==1
    assert d.tiers[0].from_cents==100000 and d.tiers[1].rate_percent==Decimal('2.345678')
    d=CommissionTiersDialog((CommissionTier(10000,Decimal('2'),0),)*2);qtbot.addWidget(d);d.persist();assert d.result()==0


def test_manual_fee_layout_keeps_save_visible(qtbot,tmp_path):
    from mi_negocio.ui.sale_dialog import SaleDialog
    c=CatalogRepository(tmp_path/'db');s=SettingsRepository(c.connection)
    d=SaleDialog(c,s,SalesRepository(c.connection));qtbot.addWidget(d);d.resize(1280,820);d.choose_method(s.list_methods()[2]);d.adjust_fee.setChecked(True);d.show();qtbot.wait(25)
    assert d.right_scroll.verticalScrollBar().maximum()==0
    assert d.save.isVisible()
    c.close()
