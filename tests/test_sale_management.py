from datetime import date
import pytest
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
from mi_negocio.storage import StorageError
from mi_negocio.inventory_repository import InventoryRepository


def setup_sale(tmp_path):
    c=CatalogRepository(tmp_path/'db');r=SalesRepository(c.connection);s=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')))
    inv=InventoryRepository(c.connection);inv.initialize('physical',{p.id:5},expected_token=inv.preview()['token'])
    m=s.list_methods()[0]
    sale=r.create(SaleDraft(date.today(),'',(SaleLineInput(p.id,2,100000),),m.id,1,customer_name='Cliente'),request_id='one',expected_method=m,receipt=ReceiptInput(date.today(),1,1000))
    return c,r,s,p,inv,m,sale


def test_edit_delete_stock_and_permissions(tmp_path):
    c,r,s,p,inv,m,sale=setup_sale(tmp_path)
    with pytest.raises(StorageError):r.delete(sale['id'])
    r.save_detail(sale['id'],invoice_ref='',has_withholding=False,tracking_number='',lines=(SaleLineInput(p.id,3,200000),))
    assert r.get(sale['id'])['total_cents']==600000
    assert r.get(sale['id'])['receipt']['commission_cents']==1000
    assert inv.rows()[0]['available']==2
    assert len(r.history(sale['id']))==1
    with pytest.raises(StorageError):r.save_detail(sale['id'],invoice_ref='',has_withholding=False,tracking_number='',lines=(SaleLineInput(p.id,6,200000),))
    assert inv.rows()[0]['available']==2
    assert r.get(sale['id'])['total_cents']==600000
    r.set_permission('delete',True);r.delete(sale['id'])
    assert inv.rows()[0]['available']==5
    assert not c.connection.execute('SELECT * FROM receipts').fetchall()
    new=r.create(SaleDraft(date.today(),'',(SaleLineInput(p.id,1,100000),),m.id,1,customer_name='Cliente'),request_id='two',expected_method=m)
    assert new['id']>sale['id']
    r.cancel(new['id']);r.delete(new['id'])
    assert inv.rows()[0]['available']==5
    c.close()


def test_disable_edit_and_cancel(tmp_path):
    c,r,s,p,inv,m,sale=setup_sale(tmp_path)
    r.set_permission('edit',False);r.set_permission('cancel',False)
    with pytest.raises(StorageError):r.save_detail(sale['id'],invoice_ref='x',has_withholding=False,tracking_number='')
    with pytest.raises(StorageError):r.cancel(sale['id'])
    assert r.get(sale['id'])['invoice_ref']==''
    c.close()


def test_settings_warning_and_detail_delete(qtbot,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from mi_negocio.ui.settings_page import SettingsPage
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    c,r,s,p,inv,m,sale=setup_sale(tmp_path)
    page=SettingsPage(s);qtbot.addWidget(page)
    control=page.sale_permissions['delete']
    assert not control.isChecked()
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:QMessageBox.No)
    control.click()
    assert not control.isChecked() and not r.permissions()['delete']
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:QMessageBox.Yes)
    control.click()
    assert control.isChecked() and r.permissions()['delete']
    detail=SaleDetailDialog(sale['id'],s,r);qtbot.addWidget(detail)
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:QMessageBox.No)
    detail.delete_sale()
    assert r.get(sale['id'])
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:QMessageBox.Yes)
    detail.delete_sale()
    with pytest.raises(StorageError):r.get(sale['id'])
    c.close()


def test_service_sale_corrected_to_product_controls_stock(tmp_path):
    c,r,s,p,inv,m,sale=setup_sale(tmp_path)
    service=c.create(validate_product(ProductInput('S','Servicio','service','1000')))
    row=r.create(SaleDraft(date.today(),'',(SaleLineInput(service.id,1,100000),),m.id,1,customer_name='Cliente'),request_id='service',expected_method=m)
    r.save_detail(row['id'],invoice_ref='',has_withholding=False,tracking_number='',lines=(SaleLineInput(p.id,1,100000),))
    assert inv.rows()[0]['available']==2
    r.cancel(row['id'])
    assert inv.rows()[0]['available']==3
    c.close()


def test_edit_vat_retention_money_and_rollback(tmp_path):
    from decimal import Decimal
    from mi_negocio.money_repository import MoneyRepository
    c,r,s,p,inv,m,first=setup_sale(tmp_path)
    draft=SaleDraft(date.today(),'F',(SaleLineInput(p.id,1,100000),),m.id,1,customer_name='C',has_withholding=True,vat_enabled=True,vat_rate=Decimal('19'))
    sale=r.create(draft,request_id='tax',expected_method=m,receipt=ReceiptInput(date.today(),1,1000))
    changed=r.save_detail(sale['id'],invoice_ref='F2',has_withholding=True,tracking_number='',lines=(SaleLineInput(p.id,2,200000),))
    assert changed['total_cents']==476000 and changed['vat_cents']==76000
    assert changed['deposit_cents']==463100
    with pytest.raises(StorageError):
        r.save_detail(sale['id'],invoice_ref='bad',has_withholding=True,tracking_number='',lines=(SaleLineInput(p.id,1,1),))
    assert r.get(sale['id'])['invoice_ref']=='F2'
    assert inv.rows()[0]['available']==1
    r.cancel(sale['id'])
    assert inv.rows()[0]['available']==3
    c.close()


def test_historical_edit_does_not_alter_opening(tmp_path):
    c=CatalogRepository(tmp_path/'db');r=SalesRepository(c.connection);s=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')));m=s.list_methods()[0]
    sale=r.create(SaleDraft(date.today(),'',(SaleLineInput(p.id,2,100000),),m.id,1,customer_name='Cliente'),request_id='old',expected_method=m)
    inv=InventoryRepository(c.connection);inv.initialize('physical',{p.id:5},expected_token=inv.preview()['token'])
    r.save_detail(sale['id'],invoice_ref='',has_withholding=False,tracking_number='',lines=(SaleLineInput(p.id,3,100000),))
    assert inv.rows()[0]['available']==5
    r.set_permission('delete',True);r.delete(sale['id'])
    assert inv.rows()[0]['available']==5
    c.close()


def test_lines_editor_stages_then_save(qtbot,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QDialog
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    from mi_negocio.ui.sale_lines_dialog import SaleLinesDialog
    c,r,s,p,inv,m,sale=setup_sale(tmp_path)
    editor=SaleLinesDialog(c.connection,(SaleLineInput(p.id,2,100000),));qtbot.addWidget(editor)
    editor.rows[0][1].setValue(3);editor.rows[0][2].setText('2000');editor.apply()
    assert editor.result_lines==(SaleLineInput(p.id,3,200000),)
    assert r.get(sale['id'])['total_cents']==200000
    detail=SaleDetailDialog(sale['id'],s,r);qtbot.addWidget(detail)
    detail.pending_lines=editor.result_lines;detail.update_summary();detail.persist()
    assert r.get(sale['id'])['total_cents']==600000
    assert inv.rows()[0]['available']==2
    c.close()


def test_reclassified_service_never_credits_unconsumed_stock(tmp_path):
    from dataclasses import replace
    c,r,s,p,inv,m,sale=setup_sale(tmp_path)
    service=c.create(validate_product(ProductInput('S','Servicio','service','1000')))
    row=r.create(SaleDraft(date.today(),'',(SaleLineInput(service.id,2,100000),),m.id,1,customer_name='Cliente'),request_id='service',expected_method=m)
    c.update(service.id,validate_product(ProductInput('S','Ahora producto','product','1000')))
    with pytest.raises(StorageError):
        r.save_detail(row['id'],invoice_ref='',has_withholding=False,tracking_number='',lines=(SaleLineInput(service.id,1,100000),))
    assert next(x for x in inv.rows() if x['id']==service.id)['available']==0
    c.close()


def test_edit_and_receive_validates_new_total(qtbot,tmp_path):
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    c,r,s,p,inv,m,first=setup_sale(tmp_path)
    row=r.create(SaleDraft(date.today(),'',(SaleLineInput(p.id,1,10000),),m.id,1,customer_name='Cliente'),request_id='pending',expected_method=m)
    detail=SaleDetailDialog(row['id'],s,r);qtbot.addWidget(detail)
    detail.pending_lines=(SaleLineInput(p.id,1,1000000),)
    detail.received.setChecked(True);detail.commission.setText('200')
    detail.persist()
    assert r.get(row['id'])['total_cents']==1000000
    assert r.get(row['id'])['receipt']['commission_cents']==20000
    c.close()


def test_delete_payments_documents_and_preserve_settings(tmp_path):
    from mi_negocio.sales import ShippingPaymentInput
    from mi_negocio.attachments import AttachmentsRepository
    from mi_negocio.money_repository import MoneyRepository
    c,r,s,p,inv,m,first=setup_sale(tmp_path)
    sale=r.create(SaleDraft(date.today(),'FE',(SaleLineInput(p.id,1,100000),),m.id,1,
        shipping_enabled=True,shipping_charged_cents=2000,shipping_cost_cents=2000,
        customer_name='C',has_withholding=True),request_id='shipping',expected_method=m,
        receipt=ReceiptInput(date.today(),1,1000),shipping_payment=ShippingPaymentInput(date.today(),1,'account'))
    docs=AttachmentsRepository(c.connection)
    source=tmp_path/'invoice.pdf';source.write_bytes(b'%PDF-1.4')
    attachment=docs.add('sale',sale['id'],source);copied=docs.path(attachment)
    money=MoneyRepository(c.connection)
    before=money.summary(date.today(),date.today())['net']
    r.set_permission('delete',True);r.delete(sale['id'])
    assert money.summary(date.today(),date.today())['net']==before-sale['deposit_cents']+2000
    assert docs.list('sale',sale['id'])==[] and copied.exists() and source.exists()
    assert not c.connection.execute('SELECT * FROM shipping_payments WHERE sale_id=?',(sale['id'],)).fetchall()
    c.close();c=CatalogRepository(tmp_path/'db');r=SalesRepository(c.connection)
    assert r.permissions()['delete']
    c.close()
