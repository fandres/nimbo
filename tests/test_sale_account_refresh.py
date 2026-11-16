from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.sales import Account
from mi_negocio.ui.sale_dialog import SaleDialog

def test_account_popup_refresh_preserves_sale(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');settings=SettingsRepository(cat.connection)
    d=SaleDialog(cat,settings,SalesRepository(cat.connection));qtbot.addWidget(d)
    method=next(m for m in settings.list_methods() if m.account_kind=='bank')
    d.choose_method(method);d.account.setCurrentIndex(d.account.findData(2))
    d.customer.setText('Cliente');d.adjust_fee.setChecked(True);d.fee_rate.setText('5')
    added=settings.save_account(Account(0,'Nequi',True,'bank',False))
    cash=settings.save_account(Account(0,'Otra caja',True,'cash',False))
    assert d.account.findData(added.id)==-1
    d.account.showPopup();d.account.hidePopup()
    assert d.account.findData(added.id)>=0
    assert d.account.findData(cash.id)==-1
    assert d.account.currentData()==2 and d.selected_method.id==method.id
    assert d.customer.text()=='Cliente' and d.adjust_fee.isChecked() and d.fee_rate.text()=='5'
    settings.save_account(Account(added.id,'Nequi nuevo',True,'bank',False))
    d.account.setCurrentIndex(d.account.findData(added.id))
    d.account.showPopup();d.account.hidePopup()
    assert d.account.currentText()=='Nequi nuevo'
    settings.save_account(Account(added.id,'Nequi nuevo',False,'bank',False))
    d.account.showPopup();d.account.hidePopup()
    assert d.account.findData(added.id)==-1 and d.account.currentData() is None
    cat.close()
