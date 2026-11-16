from dataclasses import replace
from datetime import date
from decimal import Decimal
import pytest
from PySide6.QtWidgets import QApplication
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.storage import StorageError
from mi_negocio.purchases import PurchaseLineInput, PurchaseCostInput, PurchasesFilter
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.ui.purchase_dialog import PurchaseDialog
from mi_negocio.ui.purchase_cost_editor import CurrencyFields


@pytest.fixture
def form(qtbot, tmp_path):
    cat = CatalogRepository(tmp_path/'db')
    p = cat.create(validate_product(ProductInput('001','Máquina','product','1000')))
    repo = PurchasesRepository(cat.connection)
    dlg = PurchaseDialog(cat, repo)
    qtbot.addWidget(dlg); dlg.show()
    yield dlg, cat, repo, p
    dlg.close(); cat.close()


def fill(dlg, p):
    dlg.supplier.setText('Proveedor')
    dlg.lines = [PurchaseLineInput(p.id,2,30000,'USD',Decimal('4200'),date.today())]
    dlg.cost_editor.set_costs((PurchaseCostInput('taxes','',40000000),))
    dlg.refresh_lines(); dlg.refresh_summary()


def test_form_create_edit_cancel_and_failure(form, qtbot, monkeypatch):
    dlg, cat, repo, p = form
    fill(dlg,p)
    assert '2.920.000' in dlg.summary_labels[-1].text()
    original = repo.create
    def fail(*a, **kw): raise StorageError('ocupada')
    monkeypatch.setattr(repo,'create',fail)
    dlg.save()
    assert dlg.isVisible() and dlg.error.text() == 'ocupada'
    assert dlg.supplier.text() == 'Proveedor' and dlg.save_button.isEnabled()
    monkeypatch.setattr(repo,'create',original)
    dlg.save()
    row = repo.list_purchases()[0]
    assert row['total_cents'] == 292000000
    edit = PurchaseDialog(cat,repo,purchase_id=row['id']); qtbot.addWidget(edit)
    edit.supplier.setText('Otro'); edit.reject()
    assert repo.get(row['id'])['supplier'] == 'Proveedor'
    edit = PurchaseDialog(cat,repo,purchase_id=row['id']); qtbot.addWidget(edit)
    edit.supplier.setText('Corregido'); edit.save()
    assert repo.get(row['id'])['revision'] == 2


def test_currency_switch_clears_rate_and_invalid_summary(form, qtbot):
    dlg, cat, repo, p = form
    fields = CurrencyFields(); qtbot.addWidget(fields)
    fields.currency.setCurrentText('USD'); fields.rate.setText('4200')
    fields.currency.setCurrentText('COP')
    assert fields.rate.text() == '' and fields.values()[1] is None
    fields.currency.setCurrentText('USD')
    from mi_negocio.catalog import ValidationError
    with pytest.raises(ValidationError): fields.values()
    fill(dlg,p)
    dlg.lines = [replace(dlg.lines[0], exchange_rate=None)]
    dlg.refresh_summary()
    assert all(label.text() == 'Revisa los importes' for label in dlg.summary_labels)


@pytest.mark.parametrize('width,height',[(1440,900),(1280,720),(800,560)])
def test_form_geometry(form, width, height):
    dlg, cat, repo, p = form
    fill(dlg,p); dlg.resize(width,height)
    for _ in range(3): QApplication.processEvents()
    assert dlg.rect().contains(dlg.save_button.mapTo(dlg,dlg.save_button.rect().center()))
    assert dlg.scroll.horizontalScrollBar().maximum() == 0
    if width >= 1280: assert dlg.scroll.verticalScrollBar().maximum() == 0


def test_new_line_search_does_not_select_or_copy_sale_price(form, qtbot):
    dlg, cat, repo, p = form
    editor = dlg.open_line_editor(); qtbot.addWidget(editor)
    assert editor.product.currentIndex() == -1
    assert editor.amount.text() == ''
    editor.product.setCurrentIndex(0)
    assert editor.amount.text() == ''
    editor.amount.setText('100'); editor.accept_line()
    assert dlg.lines[0].product_id == p.id


def test_cancelled_is_read_only(form, qtbot):
    dlg, cat, repo, p = form
    fill(dlg,p); dlg.save()
    row = repo.list_purchases()[0]
    repo.cancel(row['id'],'Prueba',expected_revision=1)
    view = PurchaseDialog(cat,repo,purchase_id=row['id']); qtbot.addWidget(view); view.show()
    assert not view.save_button.isVisible()
    assert not view.supplier.isEnabled()


def test_enter_applies_line_and_cost_instead_of_cancelling(form, qtbot):
    from PySide6.QtCore import Qt
    from mi_negocio.ui.purchase_cost_editor import CostDialog
    dlg,cat,repo,p=form
    line=dlg.open_line_editor(); qtbot.addWidget(line)
    line.product.setCurrentIndex(0); line.amount.setText('100')
    line.amount.setFocus(); qtbot.keyClick(line.amount,Qt.Key_Return)
    assert len(dlg.lines)==1
    cost=CostDialog(parent=dlg); qtbot.addWidget(cost); cost.show()
    cost.amount.setText('500'); cost.amount.setFocus(); qtbot.keyClick(cost.amount,Qt.Key_Return)
    assert cost.result_cost is not None
    assert cost.result_cost.amount_cents==50000


def test_line_preview_does_not_need_another_database_read(form,monkeypatch):
    dlg,cat,repo,p=form
    def unavailable(*args,**kwargs): raise StorageError('La base está ocupada')
    monkeypatch.setattr(cat,'list_products',unavailable)
    dlg.lines=[PurchaseLineInput(p.id,1,10000)]
    dlg.refresh_lines()
    assert '001' in dlg.lines_table.item(0,0).text()


def test_automatic_allocations_and_progress_reopen(form,qtbot):
    dlg,cat,repo,p=form
    fill(dlg,p)
    dlg.lines=[replace(dlg.lines[0],taxes_allocated_cents=40000000)]
    dlg.progress_editor.set_states(dict(international_shipping='not_applicable',importation='not_applicable',taxes='recorded',other='not_applicable'))
    dlg.refresh_lines(); dlg.save()
    row=repo.list_purchases()[0]
    view=PurchaseDialog(cat,repo,purchase_id=row['id']); qtbot.addWidget(view)
    assert view.lines[0].taxes_allocated_cents==40000000
    assert view.draft().costs_complete
    view.cost_editor.set_costs((PurchaseCostInput('taxes','',1),)); view.save()
    assert not view.error.text() and view.lines[0].taxes_allocated_cents==1
    assert repo.get(row['id'])['revision']==2


def test_legacy_tracking_locks_after_activation(qtbot):
    from mi_negocio.ui.purchase_progress_editor import PurchaseProgressEditor
    from PySide6.QtCore import Qt
    editor=PurchaseProgressEditor(); qtbot.addWidget(editor); editor.show()
    editor.set_states(None,True)
    assert editor.is_complete()
    qtbot.mouseClick(editor.activate,Qt.LeftButton)
    assert editor.states() is not None and not editor.is_complete()
    assert not editor.activate.isEnabled()
    qtbot.mouseClick(editor.activate,Qt.LeftButton)
    assert editor.states() is not None


def test_history_shows_allocations(form,qtbot):
    from PySide6.QtWidgets import QTextEdit
    dlg,cat,repo,p=form
    fill(dlg,p); dlg.lines=[replace(dlg.lines[0],taxes_allocated_cents=40000000)]
    dlg.save(); row=repo.list_purchases()[0]
    view=PurchaseDialog(cat,repo,purchase_id=row['id']); qtbot.addWidget(view)
    view.lines=[replace(view.lines[0],taxes_allocated_cents=20000000)]; view.save()
    view.show_history()
    text=view.findChild(QTextEdit).toPlainText()
    assert 'Gastos asignados:' in text and '400.000' in text and 'Conceptos:' in text


def test_product_editor_preserves_but_does_not_edit_allocations(form, qtbot):
    from mi_negocio.ui.purchase_line_editor import PurchaseLineDialog
    dlg,cat,repo,p=form
    line=PurchaseLineInput(p.id,2,10000,taxes_allocated_cents=500)
    editor=PurchaseLineDialog([p],line);qtbot.addWidget(editor)
    assert not hasattr(editor,'allocations')
    editor.amount.setText('300');editor.accept_line()
    assert editor.result_line.taxes_allocated_cents==500


def test_cost_distribution_from_additional_costs_does_not_duplicate(form, qtbot):
    dlg,cat,repo,p=form
    fill(dlg,p)
    dlg.open_allocations();editor=dlg.allocation_dialog;qtbot.addWidget(editor)
    editor.fields[0]['taxes_allocated_cents'].setText('400000')
    editor.apply()
    assert dlg.lines[0].taxes_allocated_cents==40000000
    assert len(dlg.cost_editor.costs())==1
    assert dlg.draft().costs[0].amount_cents==40000000
    dlg.open_allocations();editor=dlg.allocation_dialog;qtbot.addWidget(editor)
    editor.fields[0]['taxes_allocated_cents'].setText('500000')
    editor.apply()
    assert editor.error.text()
    assert dlg.lines[0].taxes_allocated_cents==40000000


def test_running_total_before_save_without_supplier(form,qtbot):
    dlg,cat,repo,p=form
    editor=dlg.open_line_editor();editor.product.setCurrentIndex(0)
    editor.quantity.setValue(3);editor.amount.setText('100');editor.accept_line()
    assert '100,00' in dlg.products_total.text()
    assert dlg.lines_table.item(0,4).text() == '$ 100,00'
    assert dlg.summary_labels[-1].text() == '$ 100,00'
    assert not repo.list_purchases()
    editor=dlg.open_line_editor();editor.product.setCurrentIndex(0)
    editor.amount.setText('50');editor.accept_line()
    assert '150,00' in dlg.products_total.text()
    editor=dlg.open_line_editor(1);editor.amount.setText('75');editor.accept_line()
    assert '175,00' in dlg.products_total.text()
    dlg.cost_editor.set_costs((PurchaseCostInput('international_shipping','',2000),))
    assert dlg.summary_labels[-1].text() == '$ 195,00'
    assert '175,00' in dlg.products_total.text()
    dlg.lines_table.selectRow(1);dlg.remove_selected()
    assert '100,00' in dlg.products_total.text()
    assert dlg.summary_labels[-1].text() == '$ 120,00'
    dlg.save()
    assert not repo.list_purchases() # required supplier is still enforced
