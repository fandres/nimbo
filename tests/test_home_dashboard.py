from datetime import date
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.home_dashboard import home_snapshot,comparison_range,percentage_change

def test_comparison_clamps_month_and_handles_zero():
    assert comparison_range(date(2024,3,31))==(date(2024,2,1),date(2024,2,29))
    assert comparison_range(date(2026,1,19))==(date(2025,12,1),date(2025,12,19))
    assert percentage_change(35,100)==-65
    assert percentage_change(12,0) is None
    assert percentage_change(0,0)==0

def test_snapshot_uses_equivalent_period_and_excludes_cancelled_and_drafts(tmp_path):
    c=CatalogRepository(tmp_path/'db');s=SalesRepository(c.connection);settings=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('1','Producto','product','100')));m=settings.list_methods()[0]
    for i,(day,price) in enumerate([(date(2025,11,10),35000),(date(2025,10,10),100000),(date(2025,10,25),50000)]):
        s.create(SaleDraft(day,'',(SaleLineInput(p.id,1,price),),m.id,1,customer_name='Cliente'),request_id=str(i),expected_method=m)
    from mi_negocio.quick_entries import QuickEntriesRepository
    QuickEntriesRepository(c.connection).save('sales',{'amount':'999999'})
    data=home_snapshot(c,s,date(2025,11,19))
    assert data['sales_total']==35000 and data['sales_previous']==100000
    assert data['pending_total']==185000 and len(data['months'])==6
    assert data['months'][-2]['value']==150000
    s.cancel(1,'Prueba');data=home_snapshot(c,s,date(2025,11,19))
    assert data['sales_total']==0 and data['pending_total']==150000
    c.close()

def test_money_does_not_subtract_expenses_twice_and_unpaid_is_global(tmp_path):
    from mi_negocio.expenses import ExpenseDraft
    from mi_negocio.expenses_repository import ExpensesRepository
    from mi_negocio.money_repository import MoneyRepository
    c=CatalogRepository(tmp_path/'db');s=SalesRepository(c.connection);e=ExpensesRepository(c.connection);money=MoneyRepository(c.connection)
    money.set_opening(1,date.today(),100000);money.set_opening(2,date.today(),0)
    category=e.categories()[0]['id']
    e.save(ExpenseDraft('Pagado',20000,date.today(),category,date.today(),1),request_id='paid')
    e.save(ExpenseDraft('Pendiente anterior',50000,date(2020,1,1),category),request_id='unpaid')
    data=home_snapshot(c,s)
    assert data['expenses_total']==20000
    assert data['unpaid_total']==50000
    assert data['money']['available']==80000 and data['money']['missing']==0
    c.close()


def test_home_links_clear_old_filters_and_open_quick_receipt(qtbot,tmp_path):
    from PySide6.QtWidgets import QPushButton
    from mi_negocio.ui.main_window import MainWindow
    from mi_negocio.ui.receipt_dialog import ReceiptDialog
    from mi_negocio.sales import SalesFilter
    c=CatalogRepository(tmp_path/'db');s=SalesRepository(c.connection);settings=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('1','Producto','product','100')));m=settings.list_methods()[0]
    for i,day in enumerate([date(2020,1,1),date.today()]):
        s.create(SaleDraft(day,str(i),(SaleLineInput(p.id,1,10000),),m.id,1,customer_name='Cliente'),request_id=str(i),expected_method=m)
    w=MainWindow(c);qtbot.addWidget(w);w.show()
    page=w.sales_page;page.search.setText('No coincide');page.state.setCurrentIndex(page.state.findData(True));page.min_total.setText('99999')
    first=w.home_page.snapshot['months'][0]
    w.home_page.chart.period_requested.emit(first['start'],first['end'])
    assert w.pages.currentWidget() is page and not page.search.text() and not page.min_total.text()
    assert page.state.currentData() is None and page.use_dates.isChecked()
    assert page.start.date().toPython()==first['start']
    w.navigate('home')
    button=next(b for b in w.home_page.attention.findChildren(QPushButton) if b.text()=='Cobrar')
    button.click();assert isinstance(page.dialog,ReceiptDialog)
    assert page.dialog.sale['sold_on']=='2020-01-01'
    page.dialog.reject()
    w.home_page.all_sales_requested.emit();assert len(page.rows)==2
    w.home_page.accounts_requested.emit();assert w.pages.currentWidget() is w.money_page and w.money_page.tabs.currentIndex()==2
    w.home_page.pending_expenses_requested.emit();assert w.expenses_page.state.currentData() is False
    assert w.expenses_page.period.start.date().year()==1900
    w.close();c.close()


def test_chart_keyboard_opens_selected_month(qtbot):
    from PySide6.QtCore import Qt
    from mi_negocio.ui.home_chart import HomeChart
    chart=HomeChart();qtbot.addWidget(chart)
    rows=[dict(start=date(2025,i,1),end=date(2025,i,20),value=i*10000) for i in range(1,7)]
    chart.set_values(rows);chart.show();chart.setFocus()
    qtbot.keyClick(chart,Qt.Key_Left)
    with qtbot.waitSignal(chart.period_requested) as signal:qtbot.keyClick(chart,Qt.Key_Return)
    assert signal.args==[rows[4]['start'],rows[4]['end']]

def test_home_money_opens_global_summary(qtbot,tmp_path):
    from mi_negocio.ui.main_window import MainWindow
    c=CatalogRepository(tmp_path/'db');w=MainWindow(c);qtbot.addWidget(w)
    w.money_page.account_filter.setCurrentIndex(w.money_page.account_filter.findData(1));w.money_page.tabs.setCurrentIndex(1)
    w.home_page.money_requested.emit()
    assert w.money_page.account_filter.currentData() is None
    assert w.money_page.tabs.currentIndex()==0
    w.close();c.close()


def test_home_collection_error_is_visible(qtbot,tmp_path):
    from mi_negocio.ui.main_window import MainWindow
    c=CatalogRepository(tmp_path/'db');s=SalesRepository(c.connection);settings=SettingsRepository(c.connection)
    p=c.create(validate_product(ProductInput('1','Producto','product','100')));m=settings.list_methods()[0]
    row=s.create(SaleDraft(date.today(),'',(SaleLineInput(p.id,1,10000),),m.id,1,customer_name='Cliente'),request_id='one',expected_method=m)
    w=MainWindow(c);qtbot.addWidget(w);w.show();s.set_permission('edit',False)
    w.home_page.sale_requested.emit(row['id'],True)
    assert 'deshabilitada' in w.home_page.error_label.text()
    assert w.home_page.error_label.isVisible()
    w.close();c.close()


def test_missing_opening_is_actionable_and_clears_after_configuration(qtbot,tmp_path):
    from mi_negocio.ui.main_window import MainWindow
    from mi_negocio.ui.money_dialogs import OpeningDialog
    from mi_negocio.money_repository import MoneyRepository
    c=CatalogRepository(tmp_path/'db');w=MainWindow(c);qtbot.addWidget(w)
    home=w.home_page;money=w.money_page
    assert home.cash_value.text()=='Sin configurar'
    assert 'doble clic' in home.metric_cards[3].toolTip()
    item=money.accounts_table.item(0,4)
    assert 'saldo inicial' in item.toolTip()
    assert item.background().color().name()=='#fff3d6'
    money.accounts_table.cellDoubleClicked.emit(0,4)
    assert isinstance(money.dialog,OpeningDialog)
    money.dialog.close()
    repository=MoneyRepository(c.connection)
    for account in repository.balances():
        repository.set_opening(account['id'],date.today(),0)
    money.updated();home.refresh_summary()
    assert 'Sin configurar' not in home.cash_value.text()
    assert home.cash_detail.styleSheet()==''
    assert money.accounts_table.item(0,4).toolTip()==''
    assert money.configure_balances.isHidden()
    w.close();c.close()
