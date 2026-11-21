from datetime import date
import sys
from PySide6.QtWidgets import QTabWidget
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput, PurchaseCostInput
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.ui.purchase_dialog import PurchaseDialog
from mi_negocio.ui.purchases_page import PurchasesPage


def test_inline_states(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db'); repo=PurchasesRepository(cat.connection)
    dlg=PurchaseDialog(cat,repo);qtbot.addWidget(dlg);dlg.show()
    p=cat.create(validate_product(ProductInput('P','Producto','product','100')))
    dlg.lines=[PurchaseLineInput(p.id,1,10000)];dlg.refresh_lines()
    assert not dlg.findChildren(QTabWidget)
    dlg.cost_editor.set_costs((PurchaseCostInput('taxes','',100),))
    combo=dlg.cost_editor.state_combos['taxes']
    assert combo.isVisible()
    combo.setCurrentIndex(combo.findData('recorded'))
    assert dlg.draft().cost_states['taxes']=='recorded'
    assert 'other' in dlg.cost_editor.state_combos
    cat.close()


def test_month_filter(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    product=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    for month in (1,2):
        repo.create(PurchaseDraft(date(2024,month,1),'Proveedor','',(PurchaseLineInput(product.id,1,100),)),request_id=str(month))
    page=PurchasesPage(cat,repo);qtbot.addWidget(page)
    page.year.setCurrentIndex(page.year.findData(2024)); page.month.setCurrentIndex(1)
    assert len(page.rows)==1
    assert 'Enero 2024' in page.table.topLevelItem(0).text(0)
    assert '01/01/2024' in page.table.topLevelItem(0).text(0)
    page.month.setCurrentIndex(2); assert page.rows[0]['purchased_on']=='2024-02-01'
    page.month.setCurrentIndex(0); assert len(page.rows)==2
    cat.close()


def test_grouped_costs_keep_edit_mapping(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    dlg=PurchaseDialog(cat,repo);qtbot.addWidget(dlg);dlg.show()
    editor=dlg.cost_editor
    editor.set_costs((PurchaseCostInput('taxes','Primer cargo',100),PurchaseCostInput('taxes','Segundo cargo',200)))
    assert len(editor.state_combos)==4
    editor.state_combos['taxes'].setCurrentIndex(editor.state_combos['taxes'].findData('recorded'))
    assert dlg.draft().cost_states['taxes']=='recorded'
    row=editor.row_costs.index(1);editor.table.setCurrentCell(row,0);editor.remove_selected()
    assert len(editor.costs())==1 and editor.costs()[0].amount_cents==100
    assert editor.state_combos['taxes'].currentData()=='recorded'
    cat.close()


def test_custom_dates_clear_month(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');page=PurchasesPage(cat,PurchasesRepository(cat.connection));qtbot.addWidget(page)
    page.month.setCurrentIndex(2);page.use_dates.setChecked(True)
    assert page.month.currentData()==0
    page.month.setCurrentIndex(1)
    assert not page.use_dates.isChecked()
    cat.close()


def test_default_year_all_years_and_custom_range(qtbot,tmp_path,monkeypatch):
    from PySide6.QtCore import QDate
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    product=cat.create(validate_product(ProductInput('YEAR','Máquina','product','1')))
    year=date.today().year
    for i,day in enumerate((date(year,1,1),date.today(),date(year-1,12,31))):
        repo.create(PurchaseDraft(day,'Proveedor','',(PurchaseLineInput(product.id,1,10000),)),request_id=str(i))
    page=PurchasesPage(cat,repo);qtbot.addWidget(page)
    assert len(page.rows)==2
    assert page.date_button.text()==f'Todo el año {year}'
    assert '200,00' in page.count.text()
    page.month.setCurrentIndex(page.month.findData(-1))
    assert len(page.rows)==3 and not page.year.isEnabled()
    assert page.date_button.text()=='Todos los años'
    page.month.setCurrentIndex(0)
    page.year.setCurrentIndex(page.year.findData(year-1))
    assert len(page.rows)==1
    page.start.setDate(QDate(year-1,12,31));page.end.setDate(QDate(year,1,1))
    page.use_dates.setChecked(True)
    assert len(page.rows)==2
    page.use_dates.setChecked(False)
    assert len(page.rows)==1
    cat.close()


def _choose_open_status(qtbot, combo, value):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    index = combo.model().index(combo.findData(value), 0)
    if sys.platform == 'win32' and QApplication.platformName() == 'offscreen':
        # Qt's Windows offscreen popup ignores synthetic viewport mouse clicks,
        # including on a standalone QComboBox. Still test activation, not setCurrentIndex.
        qtbot.keyClick(combo.view(), Qt.Key_Home)
        for _ in range(index.row()):
            qtbot.keyClick(combo.view(), Qt.Key_Down)
        qtbot.keyClick(combo.view(), Qt.Key_Return)
    else:
        pos = combo.view().visualRect(index).center()
        qtbot.mouseMove(combo.view().viewport(), pos=pos)
        qtbot.mouseClick(combo.view().viewport(), Qt.LeftButton, pos=pos)


def test_legacy_received_purchase_state_opens_with_one_click_and_saves(qtbot,tmp_path):
    from PySide6.QtCore import Qt
    from mi_negocio.purchase_receipts_repository import PurchaseReceiptsRepository
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    product=cat.create(validate_product(ProductInput('CLICK','Máquina','product','1')))
    purchase=repo.create(PurchaseDraft(date.today(),'Proveedor','',
        (PurchaseLineInput(product.id,1,100),),(PurchaseCostInput('international_shipping','',500),)),request_id='click')
    PurchaseReceiptsRepository(cat.connection).receive(purchase['id'],date.today(),expected_revision=purchase['revision'])
    dlg=PurchaseDialog(cat,repo,purchase_id=purchase['id']);qtbot.addWidget(dlg);dlg.show()
    qtbot.wait(10)
    combo=dlg.cost_editor.state_combos['international_shipping']
    assert dlg.draft().cost_states is None
    assert combo.isEnabled()
    qtbot.mouseClick(combo,Qt.LeftButton)
    assert combo.view().isVisible()
    qtbot.wait(10)
    _choose_open_status(qtbot, combo, 'recorded')
    assert combo.currentData()=='recorded'
    assert dlg.draft().cost_states['international_shipping']=='recorded'
    assert dlg.draft().cost_states['taxes']=='unselected'
    assert dlg.cost_editor.dialog is None
    assert repo.get(purchase['id'])['cost_states'] is None  # Only save persists changes.
    dlg.save()
    assert repo.get(purchase['id'])['cost_states']['international_shipping']=='recorded'
    reopened=PurchaseDialog(cat,repo,purchase_id=purchase['id']);qtbot.addWidget(reopened)
    assert reopened.cost_editor.state_combos['international_shipping'].currentData()=='recorded'
    cat.close()


def test_selecting_pending_also_activates_legacy_tracking(qtbot,tmp_path):
    from PySide6.QtCore import Qt
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    dlg=PurchaseDialog(cat,repo);qtbot.addWidget(dlg);dlg.progress_editor.set_states(None,True);dlg.show();qtbot.wait(10)
    p=cat.create(validate_product(ProductInput('P','Producto','product','100')))
    dlg.lines=[PurchaseLineInput(p.id,1,10000)];dlg.refresh_lines()
    combo=dlg.cost_editor.state_combos['taxes']
    qtbot.mouseClick(combo,Qt.LeftButton)
    assert combo.view().isVisible()
    qtbot.wait(10)
    _choose_open_status(qtbot, combo, 'pending')
    assert dlg.draft().cost_states['taxes']=='pending'
    assert not dlg.draft().costs_complete
    cat.close()


def test_cancelled_purchase_states_remain_read_only(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('CANCEL','Máquina','product','1')))
    row=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,100),)),request_id='cancel')
    repo.cancel(row['id'],'Duplicada',expected_revision=row['revision'])
    dlg=PurchaseDialog(cat,repo,purchase_id=row['id']);qtbot.addWidget(dlg);dlg.show()
    assert all(not combo.isEnabled() for combo in dlg.cost_editor.state_combos.values())
    assert dlg.draft().cost_states is None
    cat.close()
