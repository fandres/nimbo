from datetime import date
import pytest
from mi_negocio.ui.sales_report import build_sales_report
from mi_negocio.ui.sales_page import SalesPage
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
from mi_negocio.catalog import ProductInput,validate_product


def sale(**kw):
    return dict(dict(id=1,sold_on='2026-10-10',customer_name='Cliente <A>',
        customer_identification='00123',invoice_ref='FE-1',method_name='Tarjeta',
        account_name='Banco',received=True,cancelled_at=None,total_cents=100000,
        has_withholding=True,withholding_cents=2500),**kw)


def test_totals_exclude_cancelled_retention_remains_informative():
    html=build_sales_report([sale(),sale(id=2,received=False,total_cents=200000,has_withholding=False,withholding_cents=0),
        sale(id=3,cancelled_at='2026-10-11',total_cents=900000,withholding_cents=22500)], [('Período','Octubre 2026')])
    assert 'Total vigente<br><b>$ 3.000,00' in html
    assert 'Recibido bruto<br><b>$ 1.000,00' in html
    assert 'Por cobrar bruto<br><b>$ 2.000,00' in html
    assert 'Retenciones<br><b>$ 25,00' in html
    assert 'Anulada' in html and 'conservan el tratamiento informativo' in html
    assert 'Cliente &lt;A&gt;' in html and '00123' in html


def test_empty_and_escape_report():
    html=build_sales_report([], [('Búsqueda','<img src="archivo">')])
    assert 'Sin ventas para estos filtros' in html and '<img' not in html
    assert '&lt;img' in html


def setup_page(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');settings=SettingsRepository(cat.connection);repo=SalesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('001','Máquina','product','100')))
    method=settings.list_methods()[0]
    for idx,(customer,retention,total) in enumerate([('Cliente elegido',True,10000),('Cliente elegido',False,10000),('Otro cliente',True,10000),('Cliente elegido',True,50000)]):
        repo.create(SaleDraft(date.today(),'FE-'+str(idx),(SaleLineInput(p.id,1,total),),method.id,1,customer_name=customer,has_withholding=retention),request_id=str(idx),expected_method=method)
    page=SalesPage(cat,settings,repo);qtbot.addWidget(page)
    return cat,page


def test_export_filters_and_invalid_range(qtbot,tmp_path,monkeypatch):
    import mi_negocio.ui.sales_page as module
    cat,page=setup_page(qtbot,tmp_path)
    page.search.setText('Cliente elegido');page.withholding.setCurrentIndex(1)
    page.max_total.setText('150');page.account.setCurrentIndex(page.account.findData(1))
    saved=[]
    monkeypatch.setattr(module,'write_money_pdf',lambda path,html,**kw:saved.append((path,html,kw)))
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**kw:(str(tmp_path/'ventas'),''))
    page.export_pdf()
    path,html,kw=saved[0]
    assert path.endswith('.pdf') and kw['title']=='Nimbo · Ventas'
    assert 'FE-0' in html and 'FE-1' not in html and 'FE-2' not in html and 'FE-3' not in html
    assert 'Con retención' in html and '150' in html
    assert not page.error.text()
    page.min_total.setText('500');page.export_pdf()
    assert len(saved)==1 and page.error.text()
    cat.close()


def test_cancel_overwrite_and_io_error(qtbot,tmp_path,monkeypatch):
    import mi_negocio.ui.sales_page as module
    cat,page=setup_page(qtbot,tmp_path)
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**kw:('',''))
    page.export_pdf();assert not page.error.text()
    path=tmp_path/'ventas.pdf';path.write_bytes(b'original')
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**kw:(str(path.with_suffix('')),''))
    monkeypatch.setattr(module.QMessageBox,'question',lambda *a,**kw:module.QMessageBox.No)
    page.export_pdf();assert path.read_bytes()==b'original'
    monkeypatch.setattr(module.QMessageBox,'question',lambda *a,**kw:module.QMessageBox.Yes)
    def fail(*a,**kw):raise OSError('Sin permiso de escritura')
    monkeypatch.setattr(module,'write_money_pdf',fail)
    page.export_pdf();assert 'Sin permiso' in page.error.text()
    cat.close()


def test_export_empty_period_and_invalid_dates(qtbot,tmp_path,monkeypatch):
    from PySide6.QtCore import QDate
    import mi_negocio.ui.sales_page as module
    cat,page=setup_page(qtbot,tmp_path)
    page.use_dates.setChecked(True)
    page.start.setDate(QDate(2020,1,1));page.end.setDate(QDate(2020,1,31))
    saved=[]
    monkeypatch.setattr(module,'write_money_pdf',lambda path,html,**kw:saved.append(html))
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**kw:(str(tmp_path/'ventas.pdf'),''))
    page.export_pdf()
    assert 'Sin ventas para estos filtros' in saved[0] and '01/01/2020' in saved[0]
    page.start.setDate(QDate(2020,2,1));page.export_pdf()
    assert len(saved)==1 and page.error.text()
    cat.close()


def test_export_state_and_cancelled_filter(qtbot,tmp_path,monkeypatch):
    import mi_negocio.ui.sales_page as module
    cat,page=setup_page(qtbot,tmp_path)
    rows=page.sales.list_sales()
    chosen=next(r for r in rows if r['invoice_ref']=='FE-0')
    page.sales.confirm_receipt(chosen['id'],ReceiptInput(date.today(),1,0))
    page.state.setCurrentIndex(page.state.findData(True))
    saved=[]
    monkeypatch.setattr(module,'write_money_pdf',lambda path,html,**kw:saved.append(html))
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**kw:(str(tmp_path/'ventas.pdf'),''))
    page.export_pdf()
    assert 'FE-0' in saved[0] and 'FE-1' not in saved[0]
    page.sales.cancel(chosen['id'],'Prueba de anulación')
    page.validity.setCurrentIndex(page.validity.findData(True));page.export_pdf()
    assert 'FE-0' in saved[1] and 'Anulada' in saved[1]
    assert 'Total vigente<br><b>$ 0,00' in saved[1] and 'Retenciones<br><b>$ 0,00' in saved[1]
    cat.close()


def test_confirmation_and_attachment_fit_actions_column(qtbot,tmp_path):
    from PySide6.QtWidgets import QPushButton
    from mi_negocio.ui.style import STYLE
    cat,page=setup_page(qtbot,tmp_path)
    page.setStyleSheet(STYLE);page.resize(1100,720);page.tabs.setCurrentIndex(1)
    page.show();qtbot.waitExposed(page)
    holder=page.table.cellWidget(0,7)
    confirm=next(b for b in holder.findChildren(QPushButton) if b.text()=='Confirmar cobro')
    assert page.table.columnWidth(7)>=holder.sizeHint().width()
    qtbot.waitUntil(lambda:confirm.width()>=confirm.sizeHint().width())
    cat.close()
