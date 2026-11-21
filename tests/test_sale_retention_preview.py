from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.ui.sale_dialog import SaleDialog
from mi_negocio.sales import SaleLineInput


def test_retention_beside_checkbox_without_payment_and_updates(qtbot,tmp_path):
    c=CatalogRepository(tmp_path/'db')
    d=SaleDialog(c,SettingsRepository(c.connection),SalesRepository(c.connection));qtbot.addWidget(d)
    d.lines=[SaleLineInput(1,1,297700000)]
    assert not d.selected_method
    d.withholding.setChecked(True)
    assert not d.withholding_amount.isHidden()
    assert d.withholding_amount.text()=='Valor retenido: $ 74.425,00'
    d.lines=[SaleLineInput(1,2,10000000)];d.recalculate()
    assert d.withholding_amount.text()=='Valor retenido: $ 5.000,00'
    d.shipping.setChecked(True);d.shipping_charged.setText('10000')
    assert d.withholding_amount.text()=='Valor retenido: $ 5.250,00'
    d.shipping_charged.setText('importe inválido')
    assert '$' not in d.withholding_amount.text()
    d.withholding.setChecked(False)
    assert d.withholding_amount.isHidden()
    c.close()


def test_invalid_product_price_clears_retention_preview(qtbot,tmp_path):
    from mi_negocio.catalog import ProductInput, validate_product
    c=CatalogRepository(tmp_path/'db')
    p=c.create(validate_product(ProductInput('P','Producto','product','100')))
    d=SaleDialog(c,SettingsRepository(c.connection),SalesRepository(c.connection));qtbot.addWidget(d)
    d.lines=[SaleLineInput(p.id,1,10000)];d.render_lines();d.withholding.setChecked(True)
    assert d.withholding_amount.text()=='Valor retenido: $ 2,50'
    d.line_editors[0][1].setText('inválido')
    assert '$' not in d.withholding_amount.text()
    d.line_editors[0][1].setText('200')
    assert d.withholding_amount.text()=='Valor retenido: $ 5,00'
    c.close()
