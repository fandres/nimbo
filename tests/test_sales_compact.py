from mi_negocio.repository import CatalogRepository
from mi_negocio.ui.main_window import MainWindow


def test_compact_totals_and_filters(qtbot,tmp_path,monkeypatch):
    cat=CatalogRepository(tmp_path/'db');window=MainWindow(cat);qtbot.addWidget(window)
    page=window.sales_page
    def row(key,total,received,cancelled=False):
        return dict(id=key,total_cents=total,received=received,cancelled_at='x' if cancelled else None,
                    commission_cents=0,actual_commission_cents=0,shipping_cost_cents=0,shipping_charged_cents=0,sold_on='2026-01-01',customer_name='Cliente',invoice_ref='',method_name='Efectivo',account_name='Caja')
    monkeypatch.setattr(page.sales,'list_sales',lambda f:[row(1,10000,True),row(2,20000,False),row(3,90000,True,True)])
    page.refresh_sales()
    assert '300,00' in page.total_amount.text()
    assert '100,00' in page.received_amount.text()
    assert '200,00' in page.pending_amount.text()
    assert page.more_button.text()=='Más filtros · 1'
    page.withholding.setCurrentIndex(1)
    assert page.more_button.text()=='Más filtros · 2'
    assert any('retención' in b.text().lower() for b in page.chip_buttons)
    page.min_total.setText('150')
    assert len(page.rows)==2
    assert '200,00' in page.total_amount.text()
    window.close();cat.close()


def test_popups_and_removable_filters(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');window=MainWindow(cat);qtbot.addWidget(window);window.navigate('sales');window.show()
    page=window.sales_page
    assert not page.more_popup.isVisible()
    before=page.table.geometry();page.more_button.click();qtbot.wait(10)
    assert page.more_popup.isVisible() and page.table.geometry()==before
    page.withholding.setCurrentIndex(1);page.more_popup.hide()
    chip=next(b for b in page.chip_buttons if 'retención' in b.text().lower());chip.click()
    assert page.withholding.currentData() is None
    page.min_total.setText('200');page.max_total.setText('100')
    assert page.error.text() and page.total_amount.text()=='—'
    page._clear_amounts();assert not page.error.text()
    window.close();cat.close()
