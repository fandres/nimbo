from datetime import date
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import PurchaseLineInput, PurchaseDraft, PurchaseCostInput, CATEGORIES
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.purchase_allocation import purchase_progress
from mi_negocio.ui.purchase_dialog import PurchaseDialog


def setup_dialog(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('P','Máquina','product','100')))
    d=PurchaseDialog(cat,repo);qtbot.addWidget(d)
    d.supplier.setText('Proveedor');d.lines=[PurchaseLineInput(p.id,1,10000)];d.refresh_lines()
    return cat,repo,d


def test_new_costs_unselected_saved_and_not_complete(qtbot,tmp_path):
    cat,repo,d=setup_dialog(qtbot,tmp_path)
    assert set(d.draft().cost_states.values())=={'unselected'}
    assert not d.draft().costs_complete
    assert all(c.currentText()=='Seleccionar…' for c in d.cost_editor.state_combos.values())
    progress=purchase_progress(d.draft())
    assert progress['pending_categories']==[]
    assert set(progress['unselected_categories'])==set(CATEGORIES)
    row=repo.create(d.draft(),request_id='new')
    reopened=PurchaseDialog(cat,repo,purchase_id=row['id']);qtbot.addWidget(reopened)
    assert set(reopened.draft().cost_states.values())=={'unselected'}
    cat.close()


def test_enter_amount_registers_and_remove_last_clears_state(qtbot,tmp_path):
    cat,repo,d=setup_dialog(qtbot,tmp_path);editor=d.cost_editor
    editor.state_combos['taxes'].setCurrentIndex(editor.state_combos['taxes'].findData('pending'))
    editor.open_editor();cost=editor.dialog
    cost.category.setCurrentIndex(cost.category.findData('taxes'));cost.amount.setText('190');cost.apply()
    assert editor.state_combos['taxes'].currentData()=='recorded'
    assert d.draft().cost_states['taxes']=='recorded'
    row=repo.create(d.draft(),request_id='amount')
    assert row['cost_states']['taxes']=='recorded'
    editor.table.setCurrentCell(editor.row_costs.index(0),0);editor.remove_selected()
    assert editor.state_combos['taxes'].currentData()=='unselected'
    cat.close()


def test_edit_category_moves_registered_status_without_changing_history(qtbot,tmp_path):
    cat,repo,d=setup_dialog(qtbot,tmp_path)
    draft=PurchaseDraft(date.today(),'Proveedor','',tuple(d.lines),
        (PurchaseCostInput('taxes','Arancel',19000),),False,{k:'pending' for k in CATEGORIES})
    row=repo.create(draft,request_id='old')
    old=PurchaseDialog(cat,repo,purchase_id=row['id']);qtbot.addWidget(old)
    assert old.draft().cost_states['taxes']=='pending'
    old.cost_editor.open_editor(0);cost=old.cost_editor.dialog
    cost.category.setCurrentIndex(cost.category.findData('international_shipping'));cost.apply()
    assert old.draft().cost_states['international_shipping']=='recorded'
    assert old.draft().cost_states['taxes']=='pending'  # explicit historical choice preserved
    assert repo.get(row['id'])['cost_states']['international_shipping']=='pending'
    cat.close()


def test_unselected_never_counts_as_complete_and_explicit_choices_work(qtbot,tmp_path):
    import pytest
    from dataclasses import replace
    from mi_negocio.catalog import ValidationError
    from mi_negocio.purchases import calculate_purchase_totals
    cat,repo,d=setup_dialog(qtbot,tmp_path)
    with pytest.raises(ValidationError):calculate_purchase_totals(replace(d.draft(),costs_complete=True))
    for combo in d.cost_editor.state_combos.values():
        combo.setCurrentIndex(combo.findData('not_applicable'))
    assert d.draft().costs_complete
    combo=d.cost_editor.state_combos['taxes'];combo.setCurrentIndex(combo.findData('pending'))
    assert purchase_progress(d.draft())['pending_categories']==['taxes']
    assert not d.draft().costs_complete
    cat.close()


def test_last_recorded_cost_moved_to_another_category_clears_original(qtbot,tmp_path):
    cat,repo,d=setup_dialog(qtbot,tmp_path)
    d.cost_editor.open_editor();cost=d.cost_editor.dialog
    cost.category.setCurrentIndex(cost.category.findData('taxes'));cost.amount.setText('100');cost.apply()
    d.cost_editor.open_editor(0);cost=d.cost_editor.dialog
    cost.category.setCurrentIndex(cost.category.findData('importation'));cost.apply()
    assert d.draft().cost_states['taxes']=='unselected'
    assert d.draft().cost_states['importation']=='recorded'
    cat.close()
