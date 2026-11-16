from datetime import date
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.sales import SaleDraft,SaleLineInput,SalesFilter

def test_optional_customer_extras_roundtrip_search_edit(tmp_path):
    c=CatalogRepository(tmp_path/'db');r=SalesRepository(c.connection);s=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')));m=s.list_methods()[0]
    draft=SaleDraft(date.today(),'',(SaleLineInput(p.id,1,100000),),m.id,1,customer_name='Cliente',customer_alias=' Taller norte · llamar por la tarde ',customer_phone=' +57 300 123 4567 ')
    row=r.create(draft,request_id='one',expected_method=m)
    assert row['customer_alias']=='Taller norte · llamar por la tarde'
    assert row['customer_phone']=='+57 300 123 4567'
    assert len(r.list_sales(SalesFilter(query='norte')))==1
    r.save_detail(row['id'],invoice_ref='',has_withholding=False,tracking_number='',customer_alias='Otro detalle',customer_phone='0300')
    assert r.get(row['id'])['customer_phone']=='0300'
    c.close()


def test_customer_extras_new_sale_and_detail(qtbot,tmp_path):
    from mi_negocio.ui.sale_dialog import SaleDialog
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    c=CatalogRepository(tmp_path/'db');r=SalesRepository(c.connection);s=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')))
    d=SaleDialog(c,s,r);qtbot.addWidget(d)
    d.customer.setText('Cliente');d.customer_extras_toggle.click()
    d.customer_alias.setText('Taller azul');d.customer_phone.setText('+57 3001234567')
    d.product.setCurrentIndex(d.product.findData(p.id));d.append_line();d.choose_method(s.list_methods()[0])
    d.persist()
    assert d.saved_id
    detail=SaleDetailDialog(d.saved_id,s,r);qtbot.addWidget(detail)
    assert detail.customer_alias.text()=='Taller azul'
    assert detail.customer_phone.text()=='+57 3001234567'
    detail.customer_alias.clear();detail.customer_phone.setText('00300');detail.persist()
    assert r.get(d.saved_id)['customer_alias']==''
    assert r.get(d.saved_id)['customer_phone']=='00300'
    c.close()
