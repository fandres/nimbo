from PySide6.QtWidgets import QMessageBox
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.inventory_repository import InventoryRepository
from mi_negocio.ui.inventory_page import InventoryPage, InventorySettings
from mi_negocio.ui.sale_dialog import SaleDialog
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.settings_repository import SettingsRepository


def context(tmp_path):
    cat=CatalogRepository(tmp_path/'db');p=cat.create(validate_product(ProductInput('001','Impresora','product','100')))
    return cat,p,InventoryRepository(cat.connection)

def test_wizard_recommends_count_once_and_can_defer(qtbot,tmp_path):
    cat,p,inv=context(tmp_path);page=InventoryPage(inv);qtbot.addWidget(page);page.show()
    page.open_setup();dialog=page.setup_dialog
    assert dialog.physical.isChecked() and 'recomendado' in dialog.physical.text().lower()
    dialog.reject();assert not inv.state()['initialized']
    page.open_setup();dialog=page.setup_dialog
    dialog.counts[p.id].setValue(3);dialog.reviewed.setChecked(True);dialog.confirm.click()
    assert inv.state()['initialized'] and inv.rows()[0]['available']==3
    assert page.table.item(0,2).text()=='3'
    page.open_setup();assert page.setup_dialog is dialog
    page.close();cat.close()

def test_settings_gate_adjustment_confirmation(qtbot,tmp_path,monkeypatch):
    cat,p,inv=context(tmp_path);preview=inv.preview();inv.initialize('physical',{p.id:3},expected_token=preview['token'])
    settings=InventorySettings(inv);qtbot.addWidget(settings);assert not settings.enabled.isChecked()
    page=InventoryPage(inv);qtbot.addWidget(page);page.show();page.table.selectRow(0)
    assert not page.adjust_button.isEnabled()
    settings.enabled.click();page.refresh();page.table.selectRow(0);assert page.adjust_button.isEnabled()
    page.open_adjust();dialog=page.adjust_dialog;dialog.quantity.setValue(2);dialog.reason.setText('Conteo')
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**kw:QMessageBox.No)
    dialog.persist();assert inv.rows()[0]['available']==3
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**kw:QMessageBox.Yes)
    dialog.persist();assert inv.rows()[0]['available']==2
    page.close();cat.close()

def test_sale_limit_repeated_lines_and_service(qtbot,tmp_path):
    cat,p,inv=context(tmp_path);s=cat.create(validate_product(ProductInput('S','Servicio','service','50')))
    inv.initialize('physical',{p.id:3},expected_token=inv.preview()['token'])
    dialog=SaleDialog(cat,SettingsRepository(cat.connection),SalesRepository(cat.connection));qtbot.addWidget(dialog)
    def add(product):
        dialog.product.setCurrentIndex(dialog.product.findData(product.id));dialog.append_line()
    add(p);assert dialog.line_editors[0][0].maximum()==3
    dialog.line_editors[0][0].setValue(2);add(p)
    assert dialog.line_editors[1][0].maximum()==1
    add(p);assert len(dialog.lines)==2
    dialog.remove_line(1);assert dialog.line_editors[0][0].maximum()==3
    add(s);assert dialog.line_editors[1][0].maximum()>3
    dialog.reject();cat.close()


def test_navigation_offers_setup_and_stops_after_confirmation(qtbot,tmp_path):
    from mi_negocio.ui.main_window import MainWindow
    cat,p,inv=context(tmp_path);w=MainWindow(cat);qtbot.addWidget(w);w.show()
    w.offer_inventory_setup();assert w.pages.currentWidget() is w.inventory_page
    dialog=w.inventory_page.setup_dialog;assert dialog.isVisible()
    dialog.reviewed.setChecked(True);dialog.confirm.click()
    w.navigate('home');w.offer_inventory_setup();assert w.pages.currentWidget() is w.home_page
    w.close();cat.close()


def test_wizard_receipts_are_readonly_and_preserves_physical_input(qtbot,tmp_path):
    from test_inventory_repository import buy
    from mi_negocio.ui.inventory_page import InventorySetup
    cat,p,inv=context(tmp_path);buy(cat,p,4)
    dialog=InventorySetup(inv);qtbot.addWidget(dialog);dialog.counts[p.id].setValue(2)
    dialog.receipts.setChecked(True)
    assert dialog.counts[p.id].value()==4 and not dialog.counts[p.id].isEnabled()
    dialog.physical.setChecked(True);assert dialog.counts[p.id].value()==2
    dialog.receipts.setChecked(True);dialog.reviewed.setChecked(True);dialog.confirm.click()
    assert inv.rows()[0]['available']==4
    cat.close()
