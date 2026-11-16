from datetime import date
import pytest
from PySide6.QtCore import QDate
from mi_negocio.ui.money_report import build_money_report, write_money_pdf
from mi_negocio.repository import CatalogRepository
from mi_negocio.money_repository import MoneyRepository
from mi_negocio.ui.money_page import MoneyPage


def movement(delta, **kw):
    return dict(dict(date='2026-10-10', concept='Aporte', account='Banco',
                     account_id=2, delta=delta, is_card=False, kind='contribution',
                     origin='money', source_id=1, detail=''), **kw)


def test_report_distinguishes_cash_transfers_credit_and_unassigned():
    rows=[movement(10000),movement(-2000,kind='withdrawal'),
          movement(-3000,kind='transfer'),movement(3000,kind='transfer',account_id=1),
          movement(-8000,is_card=True),movement(-900,account_id=None)]
    html=build_money_report(rows,date(2026,10,1),date(2026,10,31),'Todas las cuentas','',None)
    assert 'Flujo neto del filtro' in html and '$ 80,00' in html
    assert 'Transferencia interna' in html and 'Crédito' in html and 'Sin cuenta asignada' in html
    individual=build_money_report([rows[2]],date(2026,10,1),date(2026,10,31),'Banco','',2)
    assert '$ -30,00' in individual and '#fdebed' in individual


def test_empty_report_and_escaped_content():
    html=build_money_report([],date(2026,10,1),date(2026,10,31),'Banco <1>','<img src="secret">',2)
    assert 'Sin movimientos para estos filtros' in html
    assert '<img' not in html and '&lt;img' in html and 'Banco &lt;1&gt;' in html
    html=build_money_report([movement(100,concept='<b>UPS & arancel</b>')],date(2026,10,1),date(2026,10,31),'Banco','',2)
    assert '&lt;b&gt;UPS &amp; arancel&lt;/b&gt;' in html
    with pytest.raises(ValueError):
        build_money_report([],date(2026,11,1),date(2026,10,31),'Banco','',2)


def test_pdf_written_and_invalid_path_reports_error(qapp,tmp_path):
    html=build_money_report([movement(10000)],date(2026,10,1),date(2026,10,31),'Banco','',2)
    target=tmp_path/'informe.pdf';write_money_pdf(target,html)
    assert target.read_bytes().startswith(b'%PDF-') and target.stat().st_size>1000
    with pytest.raises(OSError):write_money_pdf(tmp_path/'missing'/'informe.pdf',html)


def test_export_uses_current_filters_and_cancel_does_not_write(qtbot,tmp_path,monkeypatch):
    import mi_negocio.ui.money_page as module
    cat=CatalogRepository(tmp_path/'db');repo=MoneyRepository(cat.connection)
    repo.add('contribution',date(2026,10,10),12000,'Aporte seleccionado',to_account=2,request_id='one')
    repo.add('contribution',date(2026,10,10),99000,'Otro concepto',to_account=2,request_id='two')
    repo.add('contribution',date(2026,9,10),77000,'Aporte anterior',to_account=2,request_id='three')
    page=MoneyPage(repo);qtbot.addWidget(page)
    page.period.custom.setChecked(True);page.period.start.setDate(QDate(2026,10,1));page.period.end.setDate(QDate(2026,10,31))
    page.account_filter.setCurrentIndex(page.account_filter.findData(2));page.search.setText('Aporte seleccionado')
    saved=[]
    monkeypatch.setattr(module,'write_money_pdf',lambda path,html:saved.append((str(path),html)))
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**k:('',''))
    page.export_pdf();assert saved==[]
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**k:(str(tmp_path/'informe'),''))
    page.export_pdf()
    path,html=saved[0]
    assert path.endswith('.pdf') and 'Aporte seleccionado' in html
    assert 'Otro concepto' not in html and 'Aporte anterior' not in html
    assert '$ 120,00' in html and '01/10/2026' in html
    assert not page.error.text()
    monkeypatch.setattr(module,'write_money_pdf',lambda *a:(_ for _ in ()).throw(OSError('No se puede escribir')))
    page.export_pdf();assert 'No se puede escribir' in page.error.text()
    cat.close()


def test_pdf_failure_preserves_existing_file(qapp,tmp_path,monkeypatch):
    import mi_negocio.ui.money_report as module
    path=tmp_path/'previous.pdf';path.write_bytes(b'previous report')
    def fail(*args):raise RuntimeError('Render failed')
    monkeypatch.setattr(module.QTextDocument,'print_',fail)
    with pytest.raises(RuntimeError):write_money_pdf(path,'<p>nuevo</p>')
    assert path.read_bytes()==b'previous report'


def test_appending_extension_confirms_actual_destination(qtbot,tmp_path,monkeypatch):
    import mi_negocio.ui.money_page as module
    cat=CatalogRepository(tmp_path/'db');page=MoneyPage(MoneyRepository(cat.connection));qtbot.addWidget(page)
    path=tmp_path/'existing.pdf';path.write_bytes(b'original')
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**k:(str(path.with_suffix('')),''))
    monkeypatch.setattr(module.QMessageBox,'question',lambda *a,**k:module.QMessageBox.No)
    page.export_pdf()
    assert path.read_bytes()==b'original'
    cat.close()
