from dataclasses import replace
from datetime import date
from decimal import Decimal
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput, PurchaseCostInput
from mi_negocio.purchase_allocation import automatic_allocations, allocation_summary


def draft(lines):
    return PurchaseDraft(date.today(),'Proveedor','',tuple(lines),(PurchaseCostInput('taxes','',101),))


def test_one_model_distributes_by_units_and_preserves_cents():
    d=draft([PurchaseLineInput(1,2,1000),PurchaseLineInput(1,1,2000)])
    result=automatic_allocations(d)
    assert [l.taxes_allocated_cents for l in result.lines]==[67,34]
    assert allocation_summary(result)['complete']
    assert result.lines[1].unit_cost_cents==2000
    assert d.lines[0].taxes_allocated_cents==0


def test_mixed_models_preserve_manual_distribution():
    d=draft([PurchaseLineInput(1,2,1000,taxes_allocated_cents=80),PurchaseLineInput(2,1,2000,taxes_allocated_cents=21)])
    assert automatic_allocations(d)==d


def test_recalculate_changed_removed_and_custom_cost_in_cop():
    d=replace(draft([PurchaseLineInput(1,3,1000,taxes_allocated_cents=999)]),cost_definitions={'taxes':{'name':'Impuestos','group':'other'},'custom':{'name':'Manejo','group':'shipping'}},costs=(PurchaseCostInput('custom','',100,'USD',Decimal('4000'),date.today()),))
    result=automatic_allocations(d)
    assert result.lines[0].taxes_allocated_cents==0
    assert result.lines[0].extra_allocations=={'custom':400000}
    assert automatic_allocations(replace(result,costs=())).lines[0].extra_allocations=={}


def test_repository_cost_updates_are_automatic_and_keep_history(tmp_path):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.purchases_repository import PurchasesRepository,draft_from_record
    cat=CatalogRepository(tmp_path/'db');p=cat.create(validate_product(ProductInput('A','Máquina','product','100')))
    repo=PurchasesRepository(cat.connection)
    row=repo.create(draft([PurchaseLineInput(p.id,3,1000)]),request_id='a')
    assert row['lines'][0]['taxes_allocated_cents']==101
    update=replace(draft_from_record(row),costs=(PurchaseCostInput('taxes','',202),))
    row=repo.update(row['id'],update,expected_revision=row['revision'])
    assert row['lines'][0]['taxes_allocated_cents']==202
    assert row['revisions'][0]['snapshot']['lines'][0]['taxes_allocated_cents']==101
    cat.close()


def test_ui_updates_unit_cost_immediately(qtbot,tmp_path):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.purchases_repository import PurchasesRepository
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db');p=cat.create(validate_product(ProductInput('A','Máquina','product','100')))
    dialog=PurchaseDialog(cat,PurchasesRepository(cat.connection));qtbot.addWidget(dialog)
    dialog.lines=[PurchaseLineInput(p.id,2,10000)];dialog.refresh_lines()
    dialog.cost_editor.set_costs((PurchaseCostInput('taxes','',1000),));dialog.refresh_summary()
    assert dialog.lines[0].taxes_allocated_cents==1000
    assert '105,00' in dialog.lines_table.item(0,3).text()
    assert not dialog.distribute_costs.isEnabled()
    cat.close()


def test_adding_second_model_requires_redistributing_previous_automatic_cost(qtbot,tmp_path):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.purchases_repository import PurchasesRepository
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db')
    a=cat.create(validate_product(ProductInput('A','Máquina A','product','100')))
    b=cat.create(validate_product(ProductInput('B','Máquina B','product','100')))
    dialog=PurchaseDialog(cat,PurchasesRepository(cat.connection));qtbot.addWidget(dialog)
    dialog.lines=[PurchaseLineInput(a.id,2,10000)];dialog.refresh_lines()
    dialog.cost_editor.set_costs((PurchaseCostInput('taxes','',1000),));dialog.refresh_summary()
    assert dialog.lines[0].taxes_allocated_cents==1000
    dialog.lines.append(PurchaseLineInput(b.id,1,10000));dialog.refresh_lines()
    assert allocation_summary(dialog.draft())['remaining']['taxes']==1000
    assert dialog.distribute_costs.isEnabled()
    cat.close()
