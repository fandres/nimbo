from dataclasses import replace
from datetime import date
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput, PurchaseCostInput
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.ui.purchases_report import purchase_breakdown, build_purchases_report
from mi_negocio.ui.reports_page import ReportPanel


def fixture(tmp_path):
    cat=CatalogRepository(tmp_path/'db')
    p=cat.create(validate_product(ProductInput('P','Máquina','product','100')))
    repo=PurchasesRepository(cat.connection)
    d=PurchaseDraft(date.today(),'Proveedor <especial>','Factura & 1',(PurchaseLineInput(p.id,1,119000),),
        (PurchaseCostInput('international_shipping','Flete',5000),),invoice_vat_enabled=True)
    return cat,repo,d


def test_breakdown_included_manual_and_cancelled(tmp_path):
    cat,repo,d=fixture(tmp_path)
    global_row=repo.create(d,request_id='global')
    manual=repo.create(replace(d,invoice_vat_enabled=False,costs=(PurchaseCostInput('taxes','IVA factura',19000),)),request_id='manual')
    assert purchase_breakdown(global_row)==dict(base=100000,vat=19000,other=5000,total=124000)
    assert purchase_breakdown(manual)==dict(base=119000,vat=19000,other=0,total=138000)
    repo.cancel(manual['id'],'Error',expected_revision=1)
    manual=repo.get(manual['id'])
    html=build_purchases_report([global_row,manual],[('Período','Hoy')])
    assert 'Proveedor &lt;especial&gt;' in html and 'Factura &amp; 1' in html
    assert 'Anulada' in html and '$ 1.240,00' in html
    assert 'Envío internacional' in html
    assert '$ 2.620,00' not in html
    cat.close()


def test_report_panel_filters_and_pdf(qtbot,tmp_path):
    from mi_negocio.ui.money_report import write_money_pdf
    cat,repo,d=fixture(tmp_path)
    repo.create(d,request_id='current')
    old=replace(d,purchased_on=date(2020,1,1),supplier='Antiguo')
    repo.create(old,request_id='old')
    panel=ReportPanel('purchases',cat.connection);qtbot.addWidget(panel)
    assert len(panel.rows)==1
    assert 'IVA registrado' in panel.html
    panel.search.setText('ausente');assert not panel.rows
    assert 'Sin compras' in panel.html
    panel.search.clear()
    target=tmp_path/'compras.pdf';write_money_pdf(target,panel.html,title='Compras')
    assert target.read_bytes().startswith(b'%PDF')
    cat.close()
