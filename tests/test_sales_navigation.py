from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from mi_negocio.repository import CatalogRepository
from mi_negocio.ui.main_window import MainWindow


def test_sales_and_settings_available(qtbot,tmp_path):
    repo=CatalogRepository(tmp_path/'db');w=MainWindow(repo);qtbot.addWidget(w);w.show()
    w.nav_buttons['sales'].click()
    assert w.pages.currentWidget() is w.sales_page
    w.sales_page.open_new_sale()
    assert w.sales_page.dialog.isVisible()
    w.sales_page.dialog.reject()
    w.navigate('settings');assert w.pages.currentWidget() is w.settings_page
    w.navigate('home');w.home_page.pending_requested.emit()
    assert w.sales_page.state.currentData() is False
    w.close();repo.close()


def test_open_sale_error_is_visible_from_home(qtbot,tmp_path,monkeypatch):
    from mi_negocio.storage import StorageError
    repo=CatalogRepository(tmp_path/'db');w=MainWindow(repo);qtbot.addWidget(w);w.show()
    def fail(*args,**kwargs):raise StorageError('Base ocupada')
    monkeypatch.setattr(repo,'list_products',fail)
    w.home_page.new_sale_requested.emit()
    assert w.home_page.error_label.isVisible()
    assert w.home_page.error_label.text()=='Base ocupada'
    w.close();repo.close()


def test_home_updates_after_three_sales_and_fits(qtbot,tmp_path):
    from datetime import date
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
    from mi_negocio.sales_repository import SalesRepository
    from mi_negocio.settings_repository import SettingsRepository
    repo=CatalogRepository(tmp_path/'db');p=repo.create(validate_product(ProductInput('001','Máquina','product','1000')))
    sales=SalesRepository(repo.connection);method=SettingsRepository(repo.connection).list_methods()[0]
    w=MainWindow(repo);qtbot.addWidget(w);w.resize(1320,720);w.show()
    for i in range(3):sales.create(SaleDraft(date.today(),str(i),(SaleLineInput(p.id,1,100000),),method.id,1,customer_name="Cliente de prueba"),request_id=str(i),expected_method=method)
    w.home_page.refresh_summary()
    for _ in range(3):QApplication.processEvents()
    assert '3.000' in w.home_page.sales_total.text()
    assert '3 pendientes' in w.home_page.pending_total.text()
    assert w.home_page.scroll.horizontalScrollBar().maximum()==0
    w.home_page.scroll.ensureWidgetVisible(w.home_page.catalog_button)
    sales.confirm_receipt(sales.list_sales()[0]['id'],ReceiptInput(date.today(),1,0));w.home_page.refresh_summary()
    assert '2 pendientes' in w.home_page.pending_total.text()
    w.close();repo.close()


def test_prominent_home_action_opens_sale(qtbot,tmp_path):
    repo=CatalogRepository(tmp_path/'db');w=MainWindow(repo);qtbot.addWidget(w);w.show()
    button=w.home_page.new_sale_button
    qtbot.mouseClick(button,Qt.LeftButton)
    assert w.sales_page.dialog.isVisible()
    w.sales_page.dialog.reject();w.close();repo.close()
