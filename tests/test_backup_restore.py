import json
from pathlib import Path
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.backup_archive import create_backup,BackupError
from mi_negocio.backup_restore import prepare_restore,apply_restore,recover_restore,STAGE


def fixtures(tmp_path):
    db=tmp_path/'live'/'catalog.sqlite3';c=CatalogRepository(db)
    c.create(validate_product(ProductInput('1','Original','product','100')))
    (db.parent/'Documentos').mkdir();(db.parent/'Documentos'/'old.pdf').write_bytes(b'old')
    archive=tmp_path/'old.zip';create_backup(c.connection,archive,{'sales/vat_enabled_default':False})
    c.create(validate_product(ProductInput('2','Nuevo','product','200')))
    (db.parent/'Documentos'/'new.pdf').write_bytes(b'new')
    return c,db,archive


def test_restore_includes_safety_copy_and_no_mixing(tmp_path):
    c,db,archive=fixtures(tmp_path);prefs={'sales/vat_enabled_default':True}
    safety=prepare_restore(c.connection,archive,prefs)
    assert safety.is_file();c.close()
    apply_restore(db,lambda values:prefs.update(values))
    restored=CatalogRepository(db)
    assert len(restored.list_products())==1 and not prefs['sales/vat_enabled_default']
    assert (db.parent/'Documentos'/'old.pdf').read_bytes()==b'old'
    assert not (db.parent/'Documentos'/'new.pdf').exists()
    assert not (db.parent/STAGE).exists()
    restored.close()


def test_failure_mid_swap_rolls_back_everything(tmp_path,monkeypatch):
    import mi_negocio.backup_restore as service
    c,db,archive=fixtures(tmp_path);prefs={'sales/vat_enabled_default':True}
    prepare_restore(c.connection,archive,prefs);c.close()
    original=service.os.replace;failed=False
    def fail(source,target):
        nonlocal failed
        if Path(source).name=='Documentos' and 'incoming' in Path(source).parts and not failed:
            failed=True;raise OSError('simulated disk error')
        return original(source,target)
    monkeypatch.setattr(service.os,'replace',fail)
    with pytest.raises(BackupError):apply_restore(db,lambda values:prefs.update(values))
    restored=CatalogRepository(db);assert len(restored.list_products())==2
    assert (db.parent/'Documentos'/'new.pdf').read_bytes()==b'new'
    assert prefs['sales/vat_enabled_default'];restored.close()


def test_prepared_restore_is_discarded_on_interrupted_shutdown(tmp_path):
    c,db,archive=fixtures(tmp_path)
    prepare_restore(c.connection,archive,{});c.close()
    assert recover_restore(db,lambda values:None)
    restored=CatalogRepository(db);assert len(restored.list_products())==2;restored.close()


@pytest.mark.parametrize('component',['catalog.sqlite3','Documentos','logo.png'])
def test_crash_after_swap_recovers_on_next_start(tmp_path,monkeypatch,component):
    import mi_negocio.backup_restore as service
    c,db,archive=fixtures(tmp_path)
    (db.parent/'logo.png').write_bytes(b'current logo')
    prefs={'sales/vat_enabled_default':True}
    prepare_restore(c.connection,archive,prefs);c.close()
    original=service.os.replace
    class Crash(BaseException):pass
    def crash(source,target):
        original(source,target)
        if Path(source).name==component and ('incoming' in Path(source).parts or Path(target).parent.name=='original'):
            raise Crash()
    monkeypatch.setattr(service.os,'replace',crash)
    with pytest.raises(Crash):apply_restore(db,lambda values:prefs.update(values))
    monkeypatch.setattr(service.os,'replace',original)
    recover_restore(db,lambda values:prefs.update(values))
    restored=CatalogRepository(db);assert len(restored.list_products())==2;restored.close()
    assert (db.parent/'Documentos'/'new.pdf').read_bytes()==b'new'
    assert (db.parent/'logo.png').read_bytes()==b'current logo'
    assert prefs['sales/vat_enabled_default']


def test_failure_to_create_safety_copy_does_not_modify_live_data(tmp_path,monkeypatch):
    import mi_negocio.backup_restore as service
    c,db,archive=fixtures(tmp_path)
    def fail(*args):raise BackupError('No hay espacio')
    monkeypatch.setattr(service,'create_backup',fail)
    with pytest.raises(BackupError):prepare_restore(c.connection,archive,{})
    assert len(c.list_products())==2 and not (db.parent/STAGE).exists()
    assert (db.parent/'Documentos'/'new.pdf').read_bytes()==b'new';c.close()


def test_preference_write_failure_rolls_back_files_and_preferences(tmp_path):
    c,db,archive=fixtures(tmp_path);prefs={'sales/vat_enabled_default':True}
    prepare_restore(c.connection,archive,prefs);c.close()
    def write(values):
        prefs.update(values)
        if not values['sales/vat_enabled_default']:raise OSError('preference error')
    with pytest.raises(BackupError):apply_restore(db,write)
    restored=CatalogRepository(db);assert len(restored.list_products())==2;restored.close()
    assert prefs['sales/vat_enabled_default']


def test_crash_after_commit_keeps_restored_data(tmp_path,monkeypatch):
    import mi_negocio.backup_restore as service
    c,db,archive=fixtures(tmp_path);prefs={'sales/vat_enabled_default':True}
    prepare_restore(c.connection,archive,prefs);c.close()
    original=service.write_journal
    class Crash(BaseException):pass
    def crash(stage,journal):
        original(stage,journal)
        if journal['state']=='committed':raise Crash()
    monkeypatch.setattr(service,'write_journal',crash)
    with pytest.raises(Crash):apply_restore(db,lambda values:prefs.update(values))
    recover_restore(db,lambda values:prefs.update(values))
    restored=CatalogRepository(db);assert len(restored.list_products())==1;restored.close()
    assert not (db.parent/'Documentos'/'new.pdf').exists()
    assert not prefs['sales/vat_enabled_default']
