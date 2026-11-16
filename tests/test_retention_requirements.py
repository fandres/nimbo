from PySide6.QtCore import QSettings
from mi_negocio.ui.preferences import DisplayPreferences
from mi_negocio.ui.sale_dialog import SaleDialog
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository

def test_retention_requirements_configurable(qtbot,tmp_path):
    prefs=DisplayPreferences(QSettings(str(tmp_path/'prefs'),QSettings.IniFormat))
    assert prefs.require_retention_documents()
    c=CatalogRepository(tmp_path/'db')
    d=SaleDialog(c,SettingsRepository(c.connection),SalesRepository(c.connection),preferences=prefs);qtbot.addWidget(d)
    d.customer.setText('Cliente');d.withholding.setChecked(True)
    d.validate_fields()
    assert d.invoice.property('invalid') and d.customer_email.property('invalid')
    assert d.customer_more.isChecked()
    prefs.set_require_retention_documents(False)
    assert not DisplayPreferences(QSettings(str(tmp_path/'prefs'),QSettings.IniFormat)).require_retention_documents()
    d.validate_fields()
    assert not d.invoice.property('invalid') and not d.customer_email.property('invalid')
    c.close()


def test_detail_requires_documents_and_saves_email(qtbot,tmp_path):
    from datetime import date
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.sales import SaleDraft,SaleLineInput
    from mi_negocio.ui.sale_detail_dialog import SaleDetailDialog
    c=CatalogRepository(tmp_path/'db');settings=SettingsRepository(c.connection);sales=SalesRepository(c.connection)
    p=c.create(validate_product(ProductInput('A','Máquina','product','1000')));method=settings.list_methods()[0]
    sale=sales.create(SaleDraft(date.today(),'',(SaleLineInput(p.id,1,100000),),method.id,1,customer_name='C'),request_id='a',expected_method=method)
    prefs=DisplayPreferences(QSettings(str(tmp_path/'prefs'),QSettings.IniFormat))
    d=SaleDetailDialog(sale['id'],settings,sales,preferences=prefs);qtbot.addWidget(d);d.show()
    d.withholding.setChecked(True);d.persist()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    assert not sales.get(sale['id'])['has_withholding']
    assert d.invoice.property('invalid') and d.customer_email.property('invalid')
    assert d.invoice.hasFocus()
    d.invoice.setText('FE-123');d.customer_email.setText('cliente@example.com');d.persist()
    stored=sales.get(sale['id'])
    assert stored['has_withholding'] and stored['customer_email']=='cliente@example.com'
    # Disabling the setting also permits clearing both fields on a retained sale.
    prefs.set_require_retention_documents(False)
    e=SaleDetailDialog(sale['id'],settings,sales,preferences=prefs);qtbot.addWidget(e)
    e.invoice.clear();e.customer_email.clear();e.persist()
    assert sales.get(sale['id'])['customer_email']==''
    c.close()
