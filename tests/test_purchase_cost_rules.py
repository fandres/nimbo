import pytest
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchase_cost_rules import PurchaseCostRules


def setup_catalog(tmp_path):
    c=CatalogRepository(tmp_path/'db')
    p=c.create(validate_product(ProductInput('R','Resina','product','100',subtype='Resinas')))
    q=c.create(validate_product(ProductInput('L','Láser','product','100',subtype='Máquinas')))
    return c,p,q


def test_inheritance_overrides_empty_and_union(tmp_path):
    c,p,q=setup_catalog(tmp_path);r=PurchaseCostRules(c.connection)
    subtype=c.connection.execute('SELECT subtype_id FROM products WHERE id=?',(p.id,)).fetchone()[0]
    assert set(r.definitions([p.id]))=={'international_shipping','importation','taxes','other'}
    r.save('subtype',subtype,['taxes'])
    assert set(r.definitions([p.id]))=={'taxes'}
    r.save('product',q.id,['other'])
    assert set(r.definitions([p.id,q.id]))=={'taxes','other'}
    r.save('product',p.id,[])
    assert r.definitions([p.id])=={}
    assert r.selection('product',p.id)==[]
    r.save('product',p.id,None)
    assert r.selection('product',p.id) is None
    assert set(r.definitions([p.id]))=={'taxes'}
    c.connection.execute('UPDATE catalog_options SET name=? WHERE id=?',('Resinas nuevas',subtype));c.connection.commit()
    assert set(r.definitions([p.id]))=={'taxes'}
    c.close()


def test_rules_editor_save_empty_and_restore_inheritance(qtbot,tmp_path):
    from PySide6.QtCore import Qt
    from mi_negocio.ui.purchase_cost_rules_editor import PurchaseCostRulesEditor
    c,p,q=setup_catalog(tmp_path)
    w=PurchaseCostRulesEditor(c.connection);qtbot.addWidget(w)
    w.scope.setCurrentIndex(w.scope.findData('product'))
    w.target.setCurrentIndex(w.target.findData(p.id))
    assert w.inherit.isChecked()
    w.inherit.setChecked(False)
    for i in range(w.list.count()):w.list.item(i).setCheckState(Qt.Unchecked)
    w.persist()
    assert w.rules.selection('product',p.id)==[]
    w.refresh();assert not w.inherit.isChecked()
    w.inherit.setChecked(True);w.persist()
    assert w.rules.selection('product',p.id) is None
    c.close()


def test_new_purchase_mixed_rules_preserve_costs(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    from mi_negocio.purchases_repository import PurchasesRepository
    from mi_negocio.purchases import PurchaseLineInput,PurchaseCostInput
    c,p,q=setup_catalog(tmp_path);r=PurchaseCostRules(c.connection)
    r.save('product',p.id,['taxes']);r.save('product',q.id,['other'])
    d=PurchaseDialog(c,PurchasesRepository(c.connection));qtbot.addWidget(d)
    d.lines=[PurchaseLineInput(p.id,1,10000)];d.refresh_lines()
    assert set(d.categories)=={'taxes'}
    d.lines.append(PurchaseLineInput(q.id,1,10000));d.refresh_lines()
    assert set(d.categories)=={'taxes','other'}
    d.cost_editor.set_costs([PurchaseCostInput('other','Embalaje',1000)])
    d.lines.pop();d.refresh_lines()
    assert set(d.categories)=={'taxes','other'}
    assert d.cost_editor.costs()[0].amount_cents==1000
    assert 'conserv' in d.concepts_notice.text().lower()
    d.cost_editor.set_costs([]);d.refresh_lines()
    assert set(d.categories)=={'taxes'}
    d.close();c.close()


def test_saved_order_preserves_snapshot_until_explicit_update(qtbot,tmp_path):
    from datetime import date
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput,PurchaseCostInput
    from mi_negocio.purchases_repository import PurchasesRepository
    c,p,q=setup_catalog(tmp_path);r=PurchaseCostRules(c.connection);repo=PurchasesRepository(c.connection)
    row=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,10000,taxes_allocated_cents=1000),),
                                (PurchaseCostInput('taxes','',1000),)),request_id='history')
    r.save('product',p.id,[])
    d=PurchaseDialog(c,repo,purchase_id=row['id']);qtbot.addWidget(d)
    assert set(d.categories)=={'taxes','other','importation','international_shipping'}
    d.update_concepts()
    assert set(d.categories)=={'taxes'}
    assert d.lines[0].taxes_allocated_cents==1000
    assert d.cost_editor.costs()[0].amount_cents==1000
    assert repo.get(row['id'])['total_cents']==11000
    assert len(repo.get(row['id'])['cost_definitions'])==4
    d.load();assert len(d.categories)==4
    d.close();c.close()


def test_empty_selection_can_be_saved_as_complete_purchase(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    from mi_negocio.purchases import PurchaseLineInput
    from mi_negocio.purchases_repository import PurchasesRepository
    c,p,q=setup_catalog(tmp_path);PurchaseCostRules(c.connection).save('product',p.id,[])
    repo=PurchasesRepository(c.connection);d=PurchaseDialog(c,repo);qtbot.addWidget(d)
    d.supplier.setText('Proveedor');d.lines=[PurchaseLineInput(p.id,1,10000)];d.refresh_lines()
    assert d.categories=={} and d.draft().costs_complete
    row=repo.create(d.draft(),request_id='empty')
    assert row['cost_definitions']=={} and row['total_cents']==10000
    d.close();c.close()


def test_migration_24_keeps_orders_and_creates_backup(tmp_path):
    from datetime import date
    from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput
    from mi_negocio.purchases_repository import PurchasesRepository
    c,p,q=setup_catalog(tmp_path);repo=PurchasesRepository(c.connection)
    row=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,10000),)),request_id='before')
    for scope in ('product','subtype'):c.connection.execute('DROP TABLE purchase_cost_rules_'+scope)
    c.connection.execute('PRAGMA user_version=24');c.connection.commit();c.close()
    c=CatalogRepository(tmp_path/'db')
    assert c.connection.execute('PRAGMA user_version').fetchone()[0]==25
    assert PurchasesRepository(c.connection).get(row['id'])['total_cents']==10000
    assert PurchaseCostRules(c.connection).selection('product',p.id) is None
    assert not c.connection.execute('PRAGMA foreign_key_check').fetchall()
    c.close()


def test_subtype_change_and_disabled_concepts(tmp_path):
    from mi_negocio.purchase_concepts import PurchaseConceptsRepository
    c,p,q=setup_catalog(tmp_path);r=PurchaseCostRules(c.connection)
    subtype=c.connection.execute('SELECT subtype_id FROM products WHERE id=?',(p.id,)).fetchone()[0]
    r.save('subtype',subtype,['taxes'])
    c.update(p.id,validate_product(ProductInput('R','Resina','product','100',subtype='Máquinas')))
    assert len(r.definitions([p.id]))==4
    r.save('product',p.id,['taxes'])
    PurchaseConceptsRepository(c.connection).remove('taxes')
    assert r.definitions([p.id])=={}
    c.close()


def test_typing_another_product_does_not_write_to_previous_selection(qtbot,tmp_path):
    from PySide6.QtCore import Qt
    from mi_negocio.ui.purchase_cost_rules_editor import PurchaseCostRulesEditor
    c,p,q=setup_catalog(tmp_path);w=PurchaseCostRulesEditor(c.connection);qtbot.addWidget(w)
    w.scope.setCurrentIndex(w.scope.findData('product'))
    w.target.setCurrentIndex(w.target.findData(p.id));w.inherit.setChecked(False)
    for i in range(w.list.count()):w.list.item(i).setCheckState(Qt.Unchecked)
    w.target.setEditText(w.target.itemText(w.target.findData(q.id)))
    w.persist()
    assert w.rules.selection('product',p.id) is None
    assert w.rules.selection('product',q.id) is None
    assert 'Selecciona' in w.status.text()
    c.close()
