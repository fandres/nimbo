from datetime import date
from test_inventory_repository import ctx, start, sell
from test_fifo_repository import valued_buy
from mi_negocio.profitability_repository import ProfitabilityRepository
from mi_negocio.ui.profitability_report import build_profitability_report
from mi_negocio.ui.reports_page import ReportsPage


def test_report_escapes_and_discloses_unknown(ctx):
    cat,p,s,inv=ctx;sale=sell(cat,s)
    with cat.connection:
        cat.connection.execute('UPDATE sales SET customer_name=? WHERE id=?',('<img src="file:///secret">',sale['id']))
    data=ProfitabilityRepository(cat.connection).report(date.today(),date.today())
    html=build_profitability_report(data,date.today(),date.today())
    assert '&lt;img' in html and '<img' not in html
    assert 'Sin costo trazable' in html and 'No disponible' in html
    assert 'Servicio sin costo directo registrado' in html


def test_profitability_tab_filters_and_exports_snapshot(ctx,qtbot,monkeypatch,tmp_path):
    import mi_negocio.ui.reports_page as module
    cat,p,s,inv=ctx;start(inv);valued_buy(cat,p,2,100,'a');sell(cat,p)
    page=ReportsPage(cat.connection);qtbot.addWidget(page)
    assert page.tabs.tabText(3)=='Rentabilidad'
    panel=page.panels[3]
    assert panel.rows and 'Compra #1' in panel.html
    panel.search.setText('nadie')
    assert not panel.rows and 'Sin ventas' in panel.html
    panel.search.clear();snapshot=panel.html;written=[]
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**k:(str(tmp_path/'profit.pdf'),''))
    monkeypatch.setattr(module,'write_money_pdf',lambda path,html,**k:written.append(html))
    panel.export_pdf()
    assert written==[snapshot]
