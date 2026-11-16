from dataclasses import replace
from datetime import date
from decimal import Decimal
import pytest
from mi_negocio.vat import split_vat
from mi_negocio.catalog import ProductInput,validate_product,ValidationError
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import PurchaseLineInput,PurchaseDraft,PurchaseCostInput,calculate_purchase_totals
from mi_negocio.purchases_repository import PurchasesRepository,draft_from_record
from mi_negocio.purchase_allocation import line_unit_costs
from mi_negocio.sales import SaleDraft,SaleLineInput
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.settings_repository import SettingsRepository


def test_vat_math():
    assert split_vat(10000000,True,Decimal('19'),False)==(10000000,1900000,11900000)
    assert split_vat(11900000,True,Decimal('19'),True)==(10000000,1900000,11900000)
    assert split_vat(100,True,Decimal('19'),True)==(84,16,100)
    assert split_vat(100,False,Decimal('19'),False)==(100,0,100)
    assert split_vat(100,True,Decimal('0'),True)==(100,0,100)
    for rate in ['NaN','-1','101','0.0000001']:
        with pytest.raises(ValidationError):split_vat(100,True,Decimal(rate),True)


def test_purchase_vat_roundtrip_and_no_duplicate(tmp_path):
    c=CatalogRepository(tmp_path/'db');r=PurchasesRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')))
    line=PurchaseLineInput(p.id,3,0,total_cost_cents=11900000,vat_enabled=True,vat_included=True)
    d=PurchaseDraft(date.today(),'Proveedor','F1',(line,))
    totals=calculate_purchase_totals(d)
    assert (totals.merchandise_cents,totals.vat_cents,totals.total_cents)==(10000000,1900000,11900000)
    assert line_unit_costs(line)['landed_cents'].quantize(Decimal('.01'))==(Decimal(11900000)/3).quantize(Decimal('.01'))
    row=r.create(d,request_id='a');restored=draft_from_record(row)
    assert restored.lines[0].vat_included and restored.lines[0].vat_enabled
    assert calculate_purchase_totals(restored)==totals
    assert row['totals']['vat_cents']==1900000 and row['total_cents']==11900000
    r.update(row['id'],restored,expected_revision=1)
    assert r.get(row['id'])['total_cents']==11900000
    with pytest.raises(ValidationError):calculate_purchase_totals(replace(d,costs=(PurchaseCostInput('taxes','IVA',1900000),)))
    # Explicit import VAT remains manual when product IVA is off.
    plain=replace(d,lines=(replace(line,vat_enabled=False),),costs=(PurchaseCostInput('taxes','IVA importación',1900000),))
    assert calculate_purchase_totals(plain).total_cents==13800000
    c.close()


def test_sale_vat_commission_and_snapshot(tmp_path):
    c=CatalogRepository(tmp_path/'db');s=SettingsRepository(c.connection);r=SalesRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')));m=s.list_methods()[2]
    d=SaleDraft(date.today(),'F1',(SaleLineInput(p.id,1,10000000),),m.id,2,customer_name='C',vat_enabled=True)
    row=r.create(d,request_id='a',expected_method=m)
    assert row['vat_cents']==1900000 and row['base_cents']==10000000 and row['total_cents']==11900000
    assert row['commission_cents']==517210
    d=replace(d,vat_included=True,lines=(SaleLineInput(p.id,1,11900000),))
    row=r.create(d,request_id='b',expected_method=m)
    assert row['total_cents']==11900000 and row['vat_cents']==1900000
    assert r.get(row['id'])['vat_rate']=='19'
    c.close()


def test_vat_controls_and_defaults(qtbot,tmp_path):
    from PySide6.QtCore import QSettings
    from mi_negocio.ui.preferences import DisplayPreferences
    from mi_negocio.ui.purchase_line_editor import PurchaseLineDialog
    from mi_negocio.ui.sale_dialog import SaleDialog
    prefs=DisplayPreferences(QSettings(str(tmp_path/'prefs.ini'),QSettings.IniFormat))
    assert not prefs.vat_default('sales') and not prefs.vat_default('purchases')
    prefs.set_vat_default('sales',True)
    c=CatalogRepository(tmp_path/'db');p=c.create(validate_product(ProductInput('A','Máquina','product','1000')))
    s=SettingsRepository(c.connection)
    d=SaleDialog(c,s,SalesRepository(c.connection),preferences=prefs);qtbot.addWidget(d)
    assert d.vat.enabled.isChecked()
    d.lines=[SaleLineInput(p.id,1,10000000)];d.choose_method(s.list_methods()[0]);d.recalculate()
    assert d.totals().total_cents==11900000
    d.vat.included.click()
    assert d.totals().total_cents==10000000 and d.totals().vat_cents==1596639
    e=PurchaseLineDialog([p],preferences=prefs);qtbot.addWidget(e)
    e.product.setCurrentIndex(e.product.findData(p.id));e.amount.setText('119000');e.vat.enabled.setChecked(True);e.vat.included.click();e.accept_line()
    assert e.result_line.vat_enabled and e.result_line.vat_included
    assert calculate_purchase_totals(PurchaseDraft(date.today(),'P','',(e.result_line,))).merchandise_cents==10000000
    c.close()


def test_vat_filter_report_and_rounding(tmp_path):
    from mi_negocio.sales import SalesFilter
    from mi_negocio.vat import sale_line_amounts
    from mi_negocio.ui.sales_report import build_sales_report
    c=CatalogRepository(tmp_path/'db');r=SalesRepository(c.connection);s=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')));m=s.list_methods()[0]
    d=SaleDraft(date.today(),'F1',(SaleLineInput(p.id,1,10000000),),m.id,1,customer_name='C',vat_enabled=True)
    taxed=r.create(d,request_id='taxed',expected_method=m)
    r.create(replace(d,vat_enabled=False),request_id='plain',expected_method=m)
    assert [row['id'] for row in r.list_sales(SalesFilter(vat_enabled=True))]==[taxed['id']]
    plain=r.list_sales(SalesFilter(vat_enabled=False))
    assert len(plain)==1 and plain[0]['vat_cents']==0
    html=build_sales_report(r.list_sales(),[])
    assert 'IVA: $ 19.000,00' in html
    assert 'IVA incluido en los totales vigentes' in html
    lines=[SaleLineInput(p.id,1,1) for _ in range(3)]
    assert sum(sale_line_amounts(lines,True,Decimal('19')))==4
    c.close()


def test_disabled_vat_ignores_incomplete_hidden_rate(qtbot):
    from mi_negocio.ui.vat_fields import VatFields
    control=VatFields(True);qtbot.addWidget(control)
    control.rate.clear()
    assert any(control.issues())
    control.enabled.setChecked(False)
    assert not any(control.issues())
    assert control.values()['vat_enabled'] is False
    assert control.values()['vat_rate']==Decimal('19')


def test_purchase_vat_modes_block_each_other_before_apply(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    c=CatalogRepository(tmp_path/'db')
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')))
    d=PurchaseDialog(c,PurchasesRepository(c.connection));qtbot.addWidget(d)
    d.lines=[PurchaseLineInput(p.id,1,100000,vat_enabled=True)]
    d.refresh_lines()
    d.cost_editor.open_editor()
    cost=d.cost_editor.dialog;qtbot.addWidget(cost)
    cost.category.setCurrentIndex(cost.category.findData('taxes'))
    cost.description.setText('IVA factura');cost.amount.setText('190')
    cost.apply()
    assert cost.result()!=cost.DialogCode.Accepted
    assert not d.cost_editor.costs()
    assert 'IVA' in cost.error.text()
    cost.reject()
    d.lines=[replace(d.lines[0],vat_enabled=False)]
    d.cost_editor.set_costs([PurchaseCostInput('taxes','IVA factura',19000)])
    d.refresh_lines()
    line=d.open_line_editor(0);qtbot.addWidget(line)
    assert not line.vat.enabled.isEnabled()
    line.vat.enabled.setChecked(True)  # The validation also guards programmatic changes.
    line.accept_line()
    assert line.result()!=line.DialogCode.Accepted
    assert not d.lines[0].vat_enabled
    assert 'IVA' in line.error.text()
    line.vat.enabled.setChecked(False);line.accept_line()
    assert line.result()==line.DialogCode.Accepted
    d.close();c.close()


def test_product_vat_hides_invoice_charge_and_pending_status(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    c=CatalogRepository(tmp_path/'db')
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')))
    d=PurchaseDialog(c,PurchasesRepository(c.connection));qtbot.addWidget(d)
    from mi_negocio.purchase_concepts import PurchaseConceptsRepository
    concepts=PurchaseConceptsRepository(c.connection)
    key=concepts.save('IVA','other')['key']
    definitions=concepts.definitions()
    states={key:'not_applicable' for key in definitions};states[key]='pending'
    d._set_concepts(definitions,states,False)
    d.lines=[PurchaseLineInput(p.id,1,100000,vat_enabled=True)];d.refresh_lines()
    row=d.cost_editor.row_categories.index(key)
    assert d.cost_editor.table.isRowHidden(row)
    assert d.draft().cost_states[key]=='not_applicable'
    assert d.draft().costs_complete
    d.cost_editor.open_editor();dialog=d.cost_editor.dialog;qtbot.addWidget(dialog)
    assert not dialog.category.model().item(dialog.category.findData(key)).isEnabled()
    dialog.reject()
    d.lines=[replace(d.lines[0],vat_enabled=False)];d.refresh_lines()
    assert not d.cost_editor.table.isRowHidden(row)
    assert d.draft().cost_states[key]=='pending'
    assert not d.draft().costs_complete
    d.close();c.close()
