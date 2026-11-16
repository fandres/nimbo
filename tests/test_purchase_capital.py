from datetime import date
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput,PurchaseCostInput
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.ui.purchases_page import PurchasesPage


def test_total_investment_ignores_filters_and_excludes_cancelled(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    for month in (1,2,3):
        row=repo.create(PurchaseDraft(date(2024,month,1),'Proveedor','',(PurchaseLineInput(p.id,2,100000),),
            (PurchaseCostInput('taxes','',50000),)),request_id=str(month))
    repo.cancel(row['id'],'Duplicado',expected_revision=1)
    page=PurchasesPage(cat,repo);qtbot.addWidget(page)
    assert '5.000,00' in page.capital_amount.text()
    page.year.setCurrentIndex(page.year.findData(2024));page.month.setCurrentIndex(1)
    assert len(page.rows)==1 and '5.000,00' in page.capital_amount.text()
    page.search.setText('sin resultados')
    assert not page.rows and '5.000,00' in page.capital_amount.text()
    assert 'provisional' in page.capital_hint.text().lower()
    cat.close()
