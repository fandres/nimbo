from datetime import date
from dataclasses import replace
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput
from mi_negocio.purchases_repository import PurchasesRepository, draft_from_record


def test_optional_tracking_persists_and_can_be_edited(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    saved=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,100),)),request_id='tracking')
    assert saved['tracking_number']==''
    d=PurchaseDialog(cat,repo,purchase_id=saved['id']);qtbot.addWidget(d)
    d.tracking.setText('UPS-001');d.save()
    row=repo.get(saved['id']);assert row['tracking_number']=='UPS-001'
    restored=draft_from_record(row);assert restored.tracking_number=='UPS-001'
    updated=repo.update(row['id'],replace(restored,tracking_number='UPS-002'),expected_revision=row['revision'])
    assert updated['tracking_number']=='UPS-002'
    assert updated['revisions'][-1]['snapshot']['tracking_number']=='UPS-001'
    cat.close()


def test_tracking_migration_keeps_existing_purchase(tmp_path):
    path=tmp_path/'db';cat=CatalogRepository(path);repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    row=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,2,100),)),request_id='old')
    cat.connection.execute('ALTER TABLE purchases DROP COLUMN tracking_number')
    cat.connection.execute('PRAGMA user_version=17');cat.connection.commit();cat.close()
    cat=CatalogRepository(path);saved=PurchasesRepository(cat.connection).get(row['id'])
    assert saved['tracking_number']=='' and saved['total_cents']==200
    assert list(tmp_path.glob('*.backup-*'))
    cat.close()
