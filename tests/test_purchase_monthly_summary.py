from datetime import date,timedelta
from PySide6.QtCore import QSettings
from mi_negocio.ui.preferences import DisplayPreferences
from mi_negocio.ui.main_window import MainWindow
from mi_negocio.ui.style import format_cop
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput,PurchaseCostInput
from mi_negocio.purchases_repository import PurchasesRepository


def test_optional_monthly_summary_persists_and_ignores_list_filters(qtbot,tmp_path):
    path=str(tmp_path/'preferences.ini')
    preferences=DisplayPreferences(QSettings(path,QSettings.IniFormat))
    assert not preferences.show_monthly_purchases()
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    product=cat.create(validate_product(ProductInput('01','Máquina','product','100')))
    today=date.today();previous=today.replace(day=1)-timedelta(days=1)
    for i,day in enumerate((today,previous,today)):
        row=repo.create(PurchaseDraft(day,'Proveedor','',(PurchaseLineInput(product.id,2,10000),),
            (PurchaseCostInput('taxes','',5000),)),request_id=str(i))
    repo.cancel(row['id'],'Duplicado',expected_revision=1)
    window=MainWindow(cat,preferences=preferences);qtbot.addWidget(window)
    page=window.purchases_page;window.navigate('purchases');window.show()
    assert page.monthly_summary.isHidden()
    window.settings_page.monthly_purchases.setChecked(True)
    assert not page.monthly_summary.isHidden()
    assert page.monthly_amount.text()==format_cop(25000)
    assert page.capital_amount.text()==format_cop(50000)
    page.search.setText('sin coincidencias')
    assert not page.rows
    assert page.monthly_amount.text()==format_cop(25000)
    assert DisplayPreferences(QSettings(path,QSettings.IniFormat)).show_monthly_purchases()
    window.settings_page.monthly_purchases.setChecked(False)
    assert page.monthly_summary.isHidden()
    assert not DisplayPreferences(QSettings(path,QSettings.IniFormat)).show_monthly_purchases()
    window.close();cat.close()
