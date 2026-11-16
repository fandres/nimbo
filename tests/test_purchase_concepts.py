from datetime import date
from dataclasses import replace
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput,PurchaseCostInput,calculate_purchase_totals
from mi_negocio.purchases_repository import PurchasesRepository,draft_from_record
from mi_negocio.purchase_concepts import PurchaseConceptsRepository
from mi_negocio.storage import StorageError


def test_custom_concept_persists_and_history_survives_settings(tmp_path):
    cat=CatalogRepository(tmp_path/'db');cfg=PurchaseConceptsRepository(cat.connection)
    concept=cfg.save('Seguro de carga','shipping')
    definitions=cfg.definitions()
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    states={key:'not_applicable' for key in definitions};states[concept['key']]='recorded'
    line=PurchaseLineInput(p.id,2,10000,extra_allocations={concept['key']:500})
    draft=PurchaseDraft(date.today(),'Proveedor','',(line,),(PurchaseCostInput(concept['key'],'',500),),True,states,definitions)
    repo=PurchasesRepository(cat.connection);saved=repo.create(draft,request_id='custom')
    cfg.save('Seguro nuevo nombre','other',key=concept['key']);assert cfg.remove(concept['key'])=='disabled'
    restored=draft_from_record(repo.get(saved['id']))
    assert restored.cost_definitions[concept['key']]['name']=='Seguro de carga'
    assert calculate_purchase_totals(restored).shipping_import_cents==500
    assert concept['key'] not in cfg.definitions()
    assert restored.lines[0].extra_allocations[concept['key']]==500
    unused=cfg.save('Bodegaje','other');assert cfg.remove(unused['key'])=='deleted'
    with pytest.raises(StorageError):cfg.save('  impuestos ','other')
    cat.close()


def test_settings_and_new_order_custom_costs(qtbot,tmp_path):
    from mi_negocio.ui.purchase_concepts_editor import PurchaseConceptsEditor
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db');settings=PurchaseConceptsEditor(cat.connection);qtbot.addWidget(settings)
    settings.name.setText('Bodegaje');settings.group.setCurrentIndex(settings.group.findData('other'));settings.persist()
    key=settings.key
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    repo=PurchasesRepository(cat.connection);dialog=PurchaseDialog(cat,repo);qtbot.addWidget(dialog)
    assert key in dialog.progress_editor.editors
    dialog.supplier.setText('Proveedor');dialog.lines=[PurchaseLineInput(p.id,1,10000)]
    dialog.cost_editor.open_editor();cost=dialog.cost_editor.dialog;qtbot.addWidget(cost)
    cost.category.setCurrentIndex(cost.category.findData(key));cost.amount.setText('25');cost.apply()
    dialog.open_allocations();allocation=dialog.allocation_dialog;qtbot.addWidget(allocation)
    allocation.fields[0][key].setText('25');allocation.apply();dialog.save()
    assert repo.list_purchases()[0]['total_cents']==12500
    settings.remove_selected()
    new=PurchaseDialog(cat,repo);qtbot.addWidget(new);assert key not in new.categories
    old=PurchaseDialog(cat,repo,purchase_id=dialog.purchase_id or repo.list_purchases()[0]['id']);qtbot.addWidget(old)
    assert old.categories[key]=='Bodegaje' and old.lines[0].extra_allocations[key]==2500
    cat.close()


def test_empty_config_and_custom_history(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    from PySide6.QtWidgets import QTextEdit
    cat=CatalogRepository(tmp_path/'db');cfg=PurchaseConceptsRepository(cat.connection)
    for row in cfg.list():cfg.remove(row['key'])
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    repo=PurchasesRepository(cat.connection)
    d=PurchaseDialog(cat,repo);qtbot.addWidget(d)
    assert d.categories=={}
    d.supplier.setText('Proveedor');d.lines=[PurchaseLineInput(p.id,1,10000)];d.save()
    row=repo.list_purchases()[0];assert row['cost_definitions']=={} and row['costs_complete']
    saved=repo.update(row['id'],replace(draft_from_record(row),reference='corregido'),expected_revision=1)
    view=PurchaseDialog(cat,repo,purchase_id=row['id']);qtbot.addWidget(view);view.show_history()
    # Showing history must work even with all four initial concepts disabled.
    cat.close()


def test_migration16_rolls_back_without_losing_old_costs(tmp_path,monkeypatch):
    import sqlite3
    from mi_negocio import purchase_concepts
    path=tmp_path/'db'
    cat=CatalogRepository(path);repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,10000),),(PurchaseCostInput('taxes','',2000),)),request_id='old')
    cat.connection.execute('DROP TABLE purchase_concepts')
    cat.connection.execute('ALTER TABLE purchases DROP COLUMN cost_definitions_json')
    cat.connection.execute('ALTER TABLE purchase_lines DROP COLUMN extra_allocations_json')
    cat.connection.execute('PRAGMA user_version=15');cat.connection.commit();cat.close()
    original=purchase_concepts.migrate_purchase_concepts
    def fail(c):original(c);raise sqlite3.OperationalError('rollback')
    monkeypatch.setattr(purchase_concepts,'migrate_purchase_concepts',fail)
    with pytest.raises(StorageError):CatalogRepository(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==15
        assert c.execute('SELECT amount_cents FROM purchase_costs').fetchone()[0]==2000
        assert not c.execute("SELECT name FROM sqlite_master WHERE name='purchase_concepts'").fetchone()
    monkeypatch.setattr(purchase_concepts,'migrate_purchase_concepts',original)
    cat=CatalogRepository(path)
    assert PurchasesRepository(cat.connection).list_purchases()[0]['total_cents']==12000
    assert len(PurchaseConceptsRepository(cat.connection).list())==4
    assert not cat.connection.execute('PRAGMA foreign_key_check').fetchall()
    cat.close()


def test_old_request_retries_and_cost_lookup_index(tmp_path):
    import json
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    draft=PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,10000),))
    row=repo.create(draft,request_id='retry')
    raw=json.loads(cat.connection.execute('SELECT request_payload FROM purchases WHERE id=?',(row['id'],)).fetchone()[0])
    raw.pop('cost_definitions')
    for line in raw['lines']:line.pop('extra_allocations')
    cat.connection.execute('UPDATE purchases SET request_payload=? WHERE id=?',(json.dumps(raw),row['id']));cat.connection.commit()
    assert repo.create(draft,request_id='retry')['id']==row['id']
    assert 'purchase_costs_parent' in {r[1] for r in cat.connection.execute('PRAGMA index_list(purchase_costs)')}
    cat.close()


def test_existing_order_can_add_new_concepts_without_rewriting_history(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db');cfg=PurchaseConceptsRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    repo=PurchasesRepository(cat.connection)
    definitions=cfg.definitions();states={k:'not_applicable' for k in definitions}
    saved=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,10000),),(),True,states,definitions),request_id='old-order')
    dialog=PurchaseDialog(cat,repo,purchase_id=saved['id']);qtbot.addWidget(dialog)
    iva=cfg.save('IVA','other');cfg.save('Impuestos renombrados','shipping',key='taxes')
    assert iva['key'] not in dialog.categories
    dialog.update_concepts()
    assert dialog.categories[iva['key']]=='IVA' and dialog.categories['taxes']=='Impuestos'
    assert dialog.progress_editor.states()[iva['key']]=='pending'
    assert dialog.progress_editor.states()['taxes']=='not_applicable'
    assert iva['key'] not in repo.get(saved['id'])['cost_definitions']
    dialog.load()
    assert iva['key'] not in dialog.categories
    dialog.update_concepts();dialog.update_concepts()
    dialog.cost_editor.open_editor();cost=dialog.cost_editor.dialog;qtbot.addWidget(cost)
    cost.category.setCurrentIndex(cost.category.findData(iva['key']));cost.amount.setText('19');cost.apply()
    dialog.save()
    row=repo.get(saved['id']);assert row['total_cents']==11900
    assert row['cost_definitions']['taxes']==definitions['taxes']
    assert row['costs'][0]['category']==iva['key']
    cat.close()


def test_refresh_concepts_in_open_draft_preserves_unsaved_costs(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    d=PurchaseDialog(cat,repo);qtbot.addWidget(d)
    product=cat.create(validate_product(ProductInput('RULE','Producto','product','100')))
    d.lines=[PurchaseLineInput(product.id,1,10000)];d.refresh_lines()
    cost=PurchaseCostInput('taxes','',1900)
    d.cost_editor.set_costs((cost,))
    d.progress_editor.editors['taxes'].setCurrentIndex(1)
    cfg=PurchaseConceptsRepository(cat.connection);iva=cfg.save('IVA','other')
    disabled=cfg.save('No disponible','other',enabled=False)
    d.update_concepts()
    assert iva['key'] in d.categories and disabled['key'] not in d.categories
    assert d.cost_editor.costs()==(cost,)
    assert d.progress_editor.states()['taxes']=='recorded'
    assert not repo.list_purchases()
    cat.close()
