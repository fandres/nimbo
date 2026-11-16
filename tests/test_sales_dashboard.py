from datetime import date
from PySide6.QtCore import QDate, Qt
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.ui.main_window import MainWindow
from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput


def test_tabs_filters_ranking_and_actions(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');w=MainWindow(cat);qtbot.addWidget(w);w.show();w.navigate('sales')
    page=w.sales_page
    p=cat.create(validate_product(ProductInput('A','Máquina','product','100')))
    m=page.settings.list_methods()[0]
    row=page.sales.create(SaleDraft(date.today(),'F1',(SaleLineInput(p.id,2,10000),),m.id,1,customer_name='Cliente'),request_id='one',expected_method=m)
    page.refresh_sales()
    assert page.tabs.tabText(0)=='Resumen' and page.tabs.tabText(1)=='Movimientos'
    assert page.dashboard.data['total']==20000 and page.dashboard.data['products'][0]['units']==2
    page.tabs.setCurrentIndex(1)
    assert page.table.isVisible()
    from PySide6.QtWidgets import QPushButton
    button=next(b for b in page.table.cellWidget(0,7).findChildren(QPushButton) if b.text()=='Confirmar cobro')
    assert button.text()=='Confirmar cobro'
    qtbot.mouseClick(button,Qt.LeftButton)
    assert page.dialog.sale_id==row['id'] and page.dialog.received.isChecked()
    assert not page.sales.get(row['id'])['received']
    page.dialog.reject();page.search.setText('no existe')
    assert page.dashboard.data['total']==0 and not page.rows
    page.search.clear();page.show_pending()
    assert page.tabs.currentIndex()==1 and page.state.currentData() is False
    w.close();cat.close()


def test_quick_period_and_invalid_filters_clear_dashboard(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');w=MainWindow(cat);qtbot.addWidget(w);page=w.sales_page
    assert page.month.currentData()==date.today().month
    page.last_three_months()
    today=QDate.currentDate()
    assert page.use_dates.isChecked() and page.start.date()==QDate(today.year(),today.month(),1).addMonths(-2)
    assert page.end.date()==today
    page.min_total.setText('200');page.max_total.setText('100')
    assert page.dashboard.data is None and page.error.text()
    page._clear_amounts();assert page.dashboard.data is not None
    w.close();cat.close()


def test_dashboard_fits_desktop_and_preserves_filters(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');w=MainWindow(cat);qtbot.addWidget(w);w.resize(1320,720);w.show();w.navigate('sales');page=w.sales_page
    page.search.setText('Cliente');page.withholding.setCurrentIndex(1)
    for _ in range(5):qtbot.wait(10)
    assert page.dashboard.verticalScrollBar().maximum()==0
    page.tabs.setCurrentIndex(1);page.tabs.setCurrentIndex(0)
    assert page.search.text()=='Cliente' and page.withholding.currentData() is True
    page.dashboard.kind.setCurrentIndex(1)
    assert 'servicios' in page.dashboard.rank_hint.text()
    page.dashboard.rank_metric.setCurrentIndex(1)
    assert page.dashboard.data['total']==0
    w.close();cat.close()


def test_dashboard_repository_failure_clears_values(qtbot,tmp_path,monkeypatch):
    from mi_negocio.storage import StorageError
    cat=CatalogRepository(tmp_path/'db');w=MainWindow(cat);qtbot.addWidget(w);w.show();page=w.sales_page
    def fail(*args):raise StorageError('Base ocupada')
    monkeypatch.setattr(page.sales,'list_lines',fail)
    page.refresh_sales()
    assert page.dashboard.data is None and page.dashboard.values['total'].text()=='—'
    assert page.error.text()=='Base ocupada'
    w.close();cat.close()


def test_summary_shortcuts_keep_period_and_filter_pending(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');w=MainWindow(cat);qtbot.addWidget(w);w.show();w.navigate('sales')
    page=w.sales_page;p=cat.create(validate_product(ProductInput('A','Máquina','product','100')));m=page.settings.list_methods()[0]
    for i in range(2):
        page.sales.create(SaleDraft(date.today(),'F'+str(i),(SaleLineInput(p.id,1,10000),),m.id,1,customer_name='Cliente'),request_id=str(i),expected_method=m,receipt=ReceiptInput(date.today(),1,0) if i==0 else None)
    page.search.setText('Cliente');page.refresh_sales()
    period=(page.month.currentData(),page.year.currentData())
    qtbot.mouseClick(page.dashboard.kpi_cards[1],Qt.LeftButton)
    assert page.tabs.currentIndex()==1 and len(page.rows)==2
    page.tabs.setCurrentIndex(0)
    qtbot.mouseClick(page.dashboard.kpi_cards[3],Qt.LeftButton)
    assert page.tabs.currentIndex()==1 and page.state.currentData() is False
    assert len(page.rows)==1 and not page.rows[0]['received']
    assert (page.month.currentData(),page.year.currentData())==period
    assert page.search.text()=='Cliente'
    page.tabs.setCurrentIndex(0)
    qtbot.keyClick(page.dashboard.kpi_cards[0],Qt.Key_Space)
    assert page.tabs.currentIndex()==1
    w.close();cat.close()
