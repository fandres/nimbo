from datetime import date
from dataclasses import replace
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput,PurchasesFilter
from mi_negocio.purchases_repository import PurchasesRepository,draft_from_record


def test_alias_saved_searched_and_preserved_in_history(tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    draft=PurchaseDraft(date.today(),'Guangzhou Kominson Technology Co., Ltd.','',(PurchaseLineInput(p.id,1,10000),),supplier_alias='  AlgoLaser  ')
    saved=repo.create(draft,request_id='alias')
    assert saved['supplier_alias']=='AlgoLaser'
    assert repo.list_purchases(PurchasesFilter(query='ALGOLAS'))[0]['id']==saved['id']
    assert repo.list_purchases(PurchasesFilter(query='Kominson'))[0]['id']==saved['id']
    restored=draft_from_record(saved);assert restored.supplier_alias=='AlgoLaser'
    updated=repo.update(saved['id'],replace(restored,supplier_alias='Taller'),expected_revision=1)
    assert updated['revisions'][0]['snapshot']['supplier_alias']=='AlgoLaser'
    cat.close()


def test_alias_completion_fills_full_supplier_and_optional_alias(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    repo.create(PurchaseDraft(date.today(),'Guangzhou Kominson','',(PurchaseLineInput(p.id,1,10000),),supplier_alias='AlgoLaser'),request_id='alias')
    dialog=PurchaseDialog(cat,repo);qtbot.addWidget(dialog)
    completer=dialog.supplier.completer();completer.setCompletionPrefix('Algo')
    assert completer.completionCount()==1
    from PySide6.QtCore import Qt
    dialog.show();dialog.supplier.setFocus()
    qtbot.keyClicks(dialog.supplier,'Algo')
    qtbot.keyClick(dialog.supplier,Qt.Key_Tab)
    qtbot.waitUntil(lambda: dialog.supplier.text()=='Guangzhou Kominson')
    assert dialog.supplier.text()=='Guangzhou Kominson'
    assert dialog.supplier_alias.text()=='AlgoLaser'
    alias_completer=dialog.supplier_alias.completer();alias_completer.setCompletionPrefix('Algo')
    alias_completer.activated[str].emit(alias_completer.currentCompletion())
    qtbot.waitUntil(lambda: dialog.supplier_alias.text()=='AlgoLaser')
    assert dialog.supplier_alias.text()=='AlgoLaser' and dialog.supplier.text()=='Guangzhou Kominson'
    dialog.supplier_alias.clear();dialog.lines=[PurchaseLineInput(p.id,1,10000)];dialog.save()
    assert len(repo.list_purchases())==2
    assert repo.list_purchases()[0]['supplier_alias']==''
    cat.close()


def test_alias_migration_preserves_old_orders(tmp_path,monkeypatch):
    import sqlite3
    import pytest
    from mi_negocio import database
    from mi_negocio.storage import StorageError
    path=tmp_path/'db';cat=CatalogRepository(path)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    PurchasesRepository(cat.connection).create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,10000),)),request_id='old')
    cat.connection.execute('ALTER TABLE purchases DROP COLUMN supplier_alias');cat.connection.execute('PRAGMA user_version=16');cat.connection.commit();cat.close()
    original=database.migrate_supplier_alias
    def fail(c):original(c);raise sqlite3.OperationalError('rollback')
    monkeypatch.setattr(database,'migrate_supplier_alias',fail)
    with pytest.raises(StorageError):CatalogRepository(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==16
        assert 'supplier_alias' not in {r[1] for r in c.execute('PRAGMA table_info(purchases)')}
    monkeypatch.setattr(database,'migrate_supplier_alias',original)
    cat=CatalogRepository(path);row=PurchasesRepository(cat.connection).list_purchases()[0]
    assert row['supplier_alias']=='' and row['total_cents']==10000
    assert list(tmp_path.glob('*.backup-*'))
    cat.close()


def test_supplier_popup_includes_catalog_providers_and_selects_by_click(qtbot,tmp_path):
    from PySide6.QtCore import Qt
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db');cat.add_option('brand','Algolaser')
    dialog=PurchaseDialog(cat,PurchasesRepository(cat.connection));qtbot.addWidget(dialog);dialog.show()
    dialog.supplier.setFocus();qtbot.keyClicks(dialog.supplier,'Algo')
    completer=dialog.supplier.completer()
    assert completer.completionCount()==1
    popup=completer.popup()
    assert popup.isVisible()
    index=completer.completionModel().index(0,0)
    qtbot.mouseClick(popup.viewport(),Qt.LeftButton,pos=popup.visualRect(index).center())
    qtbot.waitUntil(lambda: dialog.supplier.text()=='Algolaser')
    assert dialog.supplier.text()=='Algolaser'
    assert dialog.supplier_alias.text()==''
    cat.close()
