from datetime import date
from mi_negocio.repository import CatalogRepository
from mi_negocio.ui.main_window import MainWindow


def test_sales_month_and_custom_dates(qtbot,tmp_path,monkeypatch):
    cat=CatalogRepository(tmp_path/'db');window=MainWindow(cat);qtbot.addWidget(window)
    page=window.sales_page;captured=[]
    def read(filters): captured.append(filters);return []
    monkeypatch.setattr(page.sales,'list_sales',read)
    page.year.setCurrentIndex(page.year.findData(2024));page.month.setCurrentIndex(2)
    assert captured[-1].start==date(2024,2,1)
    assert captured[-1].end==date(2024,2,29)
    page.use_dates.setChecked(True)
    assert page.month.currentData()==0
    page.month.setCurrentIndex(1)
    assert not page.use_dates.isChecked()
    page.show_pending()
    assert page.month.currentData()==0
    assert captured[-1].start is None and captured[-1].end is None
    window.close();cat.close()


def test_year_list_and_stable_filters(qtbot,tmp_path):
    from PySide6.QtWidgets import QComboBox
    cat=CatalogRepository(tmp_path/'db');window=MainWindow(cat);qtbot.addWidget(window)
    window.navigate('sales');window.resize(1440,900);window.show()
    page=window.sales_page
    assert isinstance(page.year,QComboBox) and not page.year.isEditable()
    assert page.year.findData(date.today().year-5)>=0
    assert page.year.findData(date.today().year-6)<0
    page.year.setCurrentIndex(page.year.count()-1)
    assert page.year.findData(date.today().year-6)>=0
    assert page.year.currentData()==date.today().year
    qtbot.wait(20)
    page.date_button.click();qtbot.wait(20)
    before=page.table.geometry()
    assert all(w.isVisible() for w in page.date_fields)
    page.use_dates.setChecked(True);qtbot.wait(20)
    assert page.table.geometry()==before
    assert page.more_popup.isAncestorOf(page.withholding)
    window.close();cat.close()


def test_current_month_and_range_totals_use_filtered_sales(qtbot,tmp_path):
    from PySide6.QtCore import QDate
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
    from mi_negocio.ui.style import format_cop
    cat=CatalogRepository(tmp_path/'db');window=MainWindow(cat);qtbot.addWidget(window)
    page=window.sales_page
    product=cat.create(validate_product(ProductInput('TEST','Servicio','service','100')))
    method=next(m for m in page.settings.list_methods() if m.name=='Transferencia')
    today=date.today();first=QDate(today.year,today.month,1)
    for i,(sold_on,amount,received) in enumerate([
        (today,10000,True),(today,20000,False),
        (first.addMonths(-1).toPython(),30000,True),
        (first.addMonths(-2).toPython(),40000,False),
        (first.addMonths(-3).toPython(),50000,False),
    ]):
        draft=SaleDraft(sold_on,str(i),(SaleLineInput(product.id,1,amount),),method.id,2,customer_name='Cliente '+str(i))
        sale=page.sales.create(draft,request_id=str(i),expected_method=method)
        if received:page.sales.confirm_receipt(sale['id'],ReceiptInput(today,2,0))
    page.refresh_sales()
    assert page.month.currentData()==today.month
    assert page.year.currentData()==today.year
    assert len(page.rows)==2
    assert page.total_amount.text()==format_cop(30000)
    assert page.received_amount.text()==format_cop(10000)
    assert page.pending_amount.text()==format_cop(20000)
    assert page.date_button.text() in page.summary_caption.text()
    page.start.setDate(first.addMonths(-2));page.end.setDate(QDate(today.year,today.month,today.day))
    page.use_dates.setChecked(True)
    assert len(page.rows)==4
    assert page.total_amount.text()==format_cop(100000)
    assert page.received_amount.text()==format_cop(40000)
    assert page.pending_amount.text()==format_cop(60000)
    page.search.setText('Cliente 2')
    assert page.total_amount.text()==format_cop(30000)
    assert page.received_amount.text()==format_cop(30000)
    assert page.pending_amount.text()==format_cop(0)
    window.close();cat.close()
