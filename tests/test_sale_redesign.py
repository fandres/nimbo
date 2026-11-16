from PySide6.QtCore import QSettings,Qt
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.ui.sale_dialog import SaleDialog
from mi_negocio.ui.preferences import DisplayPreferences
from mi_negocio.ui.settings_page import SettingsPage


def setup_dialog(qtbot,tmp_path,required=False):
    cat=CatalogRepository(tmp_path/'db')
    cat.create(validate_product(ProductInput('001','Máquina láser','product','1000000')))
    settings=SettingsRepository(cat.connection);sales=SalesRepository(cat.connection)
    preferences=DisplayPreferences(QSettings(str(tmp_path/'preferences.ini'),QSettings.IniFormat))
    preferences.set_require_sale_identification(required)
    d=SaleDialog(cat,settings,sales,preferences=preferences);qtbot.addWidget(d);d.show()
    return cat,settings,sales,preferences,d


def test_inline_edits_enter_and_remove(qtbot,tmp_path):
    cat,settings,sales,prefs,d=setup_dialog(qtbot,tmp_path)
    d.product.setCurrentIndex(1);qtbot.keyClick(d.product.lineEdit(),Qt.Key_Return)
    qtbot.waitUntil(lambda:len(d.lines)==1)
    assert d.saved_id is None and d.product.currentText()==''
    d.method_buttons[1].click()
    quantity,price=d.line_editors[0];quantity.setValue(2);price.setText('1.250.000,00')
    assert d.lines[0].quantity==2 and d.lines[0].unit_price_cents==125000000
    assert d.summary.values[0].text()=='$ 2.500.000,00'
    d.customer.setText('Cliente');price.setText('inválido');d.persist()
    assert not sales.list_sales() and d.error.text()
    price.setText('1.250.000,00');d.table.cellWidget(0,4).click()
    assert not d.lines
    d.close();cat.close()


def test_document_requirement_and_persistence(qtbot,tmp_path):
    cat,settings,sales,prefs,d=setup_dialog(qtbot,tmp_path)
    assert not prefs.require_sale_identification() and d.customer_details.isHidden()
    config=SettingsPage(settings,preferences=prefs);qtbot.addWidget(config)
    config.require_identification.setChecked(True)
    assert DisplayPreferences(QSettings(str(tmp_path/'preferences.ini'),QSettings.IniFormat)).require_sale_identification()
    d.customer.setText('Cliente');d.product.setCurrentIndex(1);d.append_line();d.method_buttons[1].click();d.persist()
    assert not sales.list_sales() and 'cédula o NIT' in d.error.text()
    assert not d.customer_details.isHidden() and '*' in d.identification_caption.text()
    d.customer_identification.setText('00123-4');d.persist()
    assert sales.get(d.saved_id)['customer_identification']=='00123-4'
    config.require_identification.setChecked(False)
    assert not prefs.require_sale_identification()
    cat.close()


def test_completion_adds_only_once(qtbot,tmp_path):
    cat,settings,sales,prefs,d=setup_dialog(qtbot,tmp_path)
    d.product.lineEdit().setFocus();qtbot.keyClicks(d.product.lineEdit(),'001')
    qtbot.waitUntil(lambda:d.product.completer().popup().isVisible())
    popup=d.product.completer().popup()
    qtbot.keyClick(popup,Qt.Key_Down);qtbot.keyClick(popup,Qt.Key_Return)
    qtbot.waitUntil(lambda:len(d.lines)==1)
    qtbot.wait(20);assert len(d.lines)==1 and not sales.list_sales()
    d.close();cat.close()


def test_invalid_price_survives_removing_other_line(qtbot,tmp_path):
    cat,settings,sales,prefs,d=setup_dialog(qtbot,tmp_path)
    for _ in range(2):d.product.setCurrentIndex(1);d.append_line()
    d.line_editors[0][1].setText('pendiente')
    d.product.setCurrentIndex(1);d.append_line()
    assert len(d.lines)==2 and d.line_editors[0][1].text()=='pendiente'
    d.remove_line(1)
    assert d.line_editors[0][1].text()=='pendiente'
    d.customer.setText('Cliente');d.method_buttons[1].click();d.persist()
    assert not sales.list_sales()
    d.close();cat.close()


def test_redesign_expanded_invoice_layout_and_shipping_preserved(qtbot,tmp_path):
    cat,settings,sales,prefs,d=setup_dialog(qtbot,tmp_path)
    for _ in range(2):d.product.setCurrentIndex(1);d.append_line()
    d.method_buttons[1].click();qtbot.wait(20)
    assert not d.delivery_body.isHidden() and d.customer_details.isHidden()
    assert d.scroll.verticalScrollBar().maximum()==0
    assert d.right_scroll.verticalScrollBar().maximum()==0
    assert d.table.verticalScrollBar().maximum()==0
    d.shipping.setChecked(True);d.shipping_details_toggle.click()
    d.city.setText('Bogotá');d.tracking.setText('000123');d.shipping_cost.setText('42500')
    d.delivery_toggle.click()
    d.customer.setText('Cliente');d.persist()
    result=sales.get(d.saved_id)
    assert result['destination_city']=='Bogotá' and result['tracking_number']=='000123'
    assert result['shipping_cost_cents']==4250000
    cat.close()
