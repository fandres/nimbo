from datetime import date
from PySide6.QtCore import QDate
from mi_negocio.repository import CatalogRepository
from mi_negocio.ui.reports_page import ReportsPage
from mi_negocio.expenses_repository import ExpensesRepository
from mi_negocio.expenses import ExpenseDraft


def setup(qtbot,tmp_path):
    repo=CatalogRepository(tmp_path/'db')
    expenses=ExpensesRepository(repo.connection)
    category=expenses.categories()[0]['id']
    expenses.save(ExpenseDraft('Informe elegido',12345,date.today(),category),request_id='one')
    page=ReportsPage(repo.connection);qtbot.addWidget(page)
    return repo,page


def test_filters_independent_and_invalid_range_clears(qtbot,tmp_path):
    repo,page=setup(qtbot,tmp_path)
    sales,expenses,money,profitability,purchases,retentions=page.panels
    assert sales.start.date().day()==1
    assert 'Informe elegido' in expenses.html
    expenses.search.setText('inexistente')
    assert 'Sin gastos' in expenses.html and not sales.search.text()
    expenses.search.clear()
    expenses.end.setDate(expenses.start.date().addDays(-1))
    assert not expenses.html and not expenses.export_button.isEnabled()
    assert expenses.error.text()
    repo.close()


def test_export_is_preview_and_cancel_preserves(qtbot,tmp_path,monkeypatch):
    import mi_negocio.ui.reports_page as module
    repo,page=setup(qtbot,tmp_path);panel=page.panels[1]
    snapshot=panel.html;written=[]
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**kw:(str(tmp_path/'reporte'),''))
    monkeypatch.setattr(module,'write_money_pdf',lambda path,html,**kw:written.append((path,html)))
    panel.export_pdf()
    assert written==[(str(tmp_path/'reporte.pdf'),snapshot)]
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**kw:('',''))
    panel.export_pdf();assert len(written)==1
    repo.close()


def test_navigation(qtbot,tmp_path):
    from mi_negocio.ui.main_window import MainWindow
    repo=CatalogRepository(tmp_path/'db');window=MainWindow(repo);qtbot.addWidget(window)
    assert window.nav_buttons['reports'].isEnabled()
    window.navigate('reports')
    assert window.pages.currentWidget() is window.reports_page
    repo.close()


def test_query_failure_clears_preview(qtbot,tmp_path,monkeypatch):
    from mi_negocio.storage import StorageError
    repo,page=setup(qtbot,tmp_path);panel=page.panels[1]
    def fail(*a,**kw):raise StorageError('No se pudo leer')
    monkeypatch.setattr(panel.expenses,'list_movements',fail)
    panel.refresh()
    assert panel.html=='' and panel.preview.toPlainText()==''
    assert not panel.export_button.isEnabled()
    repo.close()


def test_future_month_is_not_silently_clamped(qtbot,tmp_path):
    repo,page=setup(qtbot,tmp_path);panel=page.panels[0]
    if date.today().month<12:
        panel.month.setCurrentIndex(date.today().month)
        assert not panel.html and panel.error.text()
    repo.close()


def test_sales_retention_state_and_account_filters(qtbot,tmp_path):
    from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
    from mi_negocio.catalog import ProductInput,validate_product
    repo,page=setup(qtbot,tmp_path);panel=page.panels[0]
    product=repo.create(validate_product(ProductInput('T1','Equipo','product','100')))
    method=panel.settings.list_methods()[0]
    for i in range(3):
        panel.sales.create(SaleDraft(date.today(),'FAC-'+str(i),(SaleLineInput(product.id,1,10000),),method.id,1,customer_name='Cliente '+str(i),has_withholding=i==0),request_id='sale'+str(i),expected_method=method,receipt=ReceiptInput(date.today(),1,0) if i==0 else None)
    panel.withholding.setCurrentIndex(panel.withholding.findData(True))
    assert 'FAC-0' in panel.html and 'FAC-1' not in panel.html
    panel.state.setCurrentIndex(panel.state.findData(False))
    assert 'Sin ventas' in panel.html
    panel.withholding.setCurrentIndex(0)
    assert 'FAC-0' not in panel.html and 'FAC-1' in panel.html
    panel.account.setCurrentIndex(panel.account.findData(2))
    assert 'Sin ventas' in panel.html
    repo.close()


def test_expense_filters_and_historical_options(qtbot,tmp_path):
    repo,page=setup(qtbot,tmp_path);panel=page.panels[1]
    from mi_negocio.sales import Account
    account=panel.settings.list_accounts(True)[0]
    panel.settings.save_account(Account(account.id,account.name,False,account.kind,account.is_default))
    category=panel.expenses.categories()[0]
    panel.expenses.save_category(category['id'],category['name'],False)
    panel.refresh_options()
    assert panel.account.findData(account.id)>=0
    assert panel.category.findData('manual:'+str(category['id']))>=0
    panel.state.setCurrentIndex(panel.state.findData(True))
    assert 'Sin gastos' in panel.html
    panel.state.setCurrentIndex(0)
    assert 'Informe elegido' in panel.html
    panel.date_basis.setCurrentIndex(1)
    assert 'Sin gastos' in panel.html
    repo.close()


def test_overwrite_denied_and_failure_preserves_file(qtbot,tmp_path,monkeypatch):
    import mi_negocio.ui.reports_page as module
    repo,page=setup(qtbot,tmp_path);panel=page.panels[1]
    target=tmp_path/'existing.pdf';target.write_bytes(b'original')
    monkeypatch.setattr(module.QFileDialog,'getSaveFileName',lambda *a,**kw:(str(target),''))
    monkeypatch.setattr(module.QMessageBox,'question',lambda *a,**kw:module.QMessageBox.No)
    panel.export_pdf();assert target.read_bytes()==b'original'
    monkeypatch.setattr(module.QMessageBox,'question',lambda *a,**kw:module.QMessageBox.Yes)
    def fail(*a,**kw):raise OSError('Sin permiso')
    monkeypatch.setattr(module,'write_money_pdf',fail)
    panel.export_pdf()
    assert 'Sin permiso' in panel.error.text() and target.read_bytes()==b'original'
    repo.close()


def test_quick_periods_clear_and_custom_dates(qtbot,tmp_path):
    repo,page=setup(qtbot,tmp_path);panel=page.panels[0]
    today=QDate.currentDate()
    panel.period_buttons['previous'].click()
    previous=today.addMonths(-1)
    assert panel.start.date()==QDate(previous.year(),previous.month(),1)
    assert panel.end.date()==QDate(previous.year(),previous.month(),previous.daysInMonth())
    panel.period_buttons['year'].click()
    assert panel.start.date()==QDate(today.year(),1,1) and panel.end.date()==today
    panel.search.setText('nadie');panel.state.setCurrentIndex(1)
    panel.clear_button.click()
    assert not panel.search.text() and panel.state.currentData() is None
    assert panel.start.date()==QDate(today.year(),today.month(),1)
    panel.start.setDate(QDate(2020,2,1));panel.end.setDate(QDate(2020,2,29))
    assert panel.period_buttons['custom'].isChecked()
    assert '29/02/2020' in panel.html
    assert page.panels[-1].period_buttons['year'].isChecked()
    repo.close()


def test_header_exports_active_preview_and_tracks_errors(qtbot,tmp_path,monkeypatch):
    repo,page=setup(qtbot,tmp_path)
    called=[]
    for i,panel in enumerate(page.panels):
        monkeypatch.setattr(panel,'export_pdf',lambda i=i:called.append(i))
    page.tabs.setCurrentIndex(1);page.export_button.click()
    assert called==[1]
    panel=page.panels[1];panel.end.setDate(panel.start.date().addDays(-1))
    assert not page.export_button.isEnabled()
    page.tabs.setCurrentIndex(0)
    assert page.export_button.isEnabled()
    page.export_button.click();assert called==[1,0]
    repo.close()


def test_dates_wrap_without_changing_filter_column_count(qtbot,tmp_path):
    repo,page=setup(qtbot,tmp_path);panel=page.panels[0]
    panel.arrange_filters(1100)
    panel.arrange_filters(930)
    position=panel.filters_grid.getItemPosition(panel.filters_grid.indexOf(panel.dates_bar))
    assert position==(1,0,1,2)
    panel.arrange_filters(1100)
    assert panel.filters_grid.getItemPosition(panel.filters_grid.indexOf(panel.dates_bar))==(0,1,1,1)
    repo.close()
