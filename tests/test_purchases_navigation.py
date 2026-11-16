from PySide6.QtCore import Qt
from mi_negocio.repository import CatalogRepository
from mi_negocio.ui.main_window import MainWindow
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput
from datetime import date


def test_purchase_navigation_shortcut_and_home(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db'); window=MainWindow(cat); qtbot.addWidget(window); window.show()
    assert window.nav_buttons['purchases'].isEnabled()
    window.navigate('purchases')
    page=window.purchases_page
    assert window.pages.currentWidget() is page
    assert page.new_shortcut.isEnabled() and not window.sales_page.new_shortcut.isEnabled()
    page.search.setText('texto'); window.navigate('home'); window.navigate('purchases')
    assert page.search.text()=='texto'
    window.home_page.new_purchase_requested.emit()
    assert page.dialog.isVisible()
    page.dialog.reject(); window.close(); cat.close()


def test_purchase_filters_and_stale_results(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db'); window=MainWindow(cat); qtbot.addWidget(window)
    product=cat.create(validate_product(ProductInput('001','Impresora','product','10')))
    page=window.purchases_page
    page.purchases.create(PurchaseDraft(date.today(),'Proveedor','Pedido',(PurchaseLineInput(product.id,1,10000),)),request_id='1')
    page.refresh_purchases(); assert page.table.topLevelItemCount()==1
    page.search.setText('001'); assert page.table.topLevelItemCount()==1
    page.state.setCurrentIndex(2); assert page.table.topLevelItemCount()==0
    page.state.setCurrentIndex(0); assert page.table.topLevelItemCount()==1
    page.use_dates.setChecked(True); page.end.setDate(page.start.date().addDays(-1))
    assert page.table.topLevelItemCount()==0 and page.error.text()
    window.close(); cat.close()
