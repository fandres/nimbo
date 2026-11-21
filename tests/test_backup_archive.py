from pathlib import Path
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.backup_archive import create_backup, unpack_backup, BackupError


def test_round_trip_database_documents_and_preferences(tmp_path):
    root=tmp_path/'source';c=CatalogRepository(root/'catalog.sqlite3')
    c.create(validate_product(ProductInput('1','Producto','product','100')))
    (root/'Documentos'/'2026').mkdir(parents=True)
    (root/'Documentos'/'2026'/'receipt.pdf').write_bytes(b'%PDF-test')
    (root/'logo.png').write_bytes(b'logo')
    target=tmp_path/'backup.zip'
    create_backup(c.connection,target,{'sales/vat_enabled_default':True})
    dest=tmp_path/'unpacked';manifest=unpack_backup(target,dest)
    assert manifest['preferences']=={'sales/vat_enabled_default':True}
    assert (dest/'Documentos'/'2026'/'receipt.pdf').read_bytes()==b'%PDF-test'
    copy=CatalogRepository(dest/'catalog.sqlite3')
    assert copy.list_products()[0].name=='Producto'
    copy.close();c.close()


def test_wal_and_missing_active_document(tmp_path):
    import sqlite3
    c=CatalogRepository(tmp_path/'data'/'catalog.sqlite3')
    c.connection.execute('PRAGMA journal_mode=WAL')
    c.create(validate_product(ProductInput('W','WAL','product','200')))
    create_backup(c.connection,tmp_path/'wal.zip',{})
    unpack_backup(tmp_path/'wal.zip',tmp_path/'out')
    with sqlite3.connect(tmp_path/'out'/'catalog.sqlite3') as db:
        assert db.execute('SELECT name FROM products').fetchone()[0]=='WAL'
    c.connection.execute("INSERT INTO attachments(owner_kind,owner_id,original_name,relative_path,created_at) VALUES('purchase',1,'missing','2026/missing.pdf','now')");c.connection.commit()
    with pytest.raises(BackupError,match='Falta un documento'):create_backup(c.connection,tmp_path/'bad.zip',{})
    assert not (tmp_path/'bad.zip').exists();c.close()


@pytest.mark.parametrize('attack',['hash','traversal','duplicate','future','extra','limit'])
def test_rejects_damaged_or_unsafe_archives(tmp_path,attack,monkeypatch):
    import zipfile,json,warnings
    import mi_negocio.backup_archive as module
    c=CatalogRepository(tmp_path/'data'/'catalog.sqlite3')
    create_backup(c.connection,tmp_path/'good.zip',{});c.close()
    with zipfile.ZipFile(tmp_path/'good.zip') as z:entries={n:z.read(n) for n in z.namelist()}
    manifest=json.loads(entries['manifest.json'])
    if attack=='hash':manifest['files']['catalog.sqlite3']['sha256']='0'*64
    if attack=='traversal':entries['../escape']=b'bad'
    if attack=='extra':entries['unlisted']=b'bad'
    if attack=='future':manifest['schema_version']=999
    if attack=='limit':monkeypatch.setattr(module,'MAX_FILE',1)
    entries['manifest.json']=json.dumps(manifest).encode()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        with zipfile.ZipFile(tmp_path/'bad.zip','w') as z:
            for name,data in entries.items():z.writestr(name,data)
            if attack=='duplicate':z.writestr('manifest.json',entries['manifest.json'])
    with pytest.raises(BackupError):unpack_backup(tmp_path/'bad.zip',tmp_path/'out')
    assert not (tmp_path/'out').exists() and not (tmp_path/'escape').exists()


def test_existing_archive_is_not_overwritten(tmp_path):
    c=CatalogRepository(tmp_path/'data'/'catalog.sqlite3');target=tmp_path/'backup.zip';target.write_bytes(b'keep')
    with pytest.raises(BackupError):create_backup(c.connection,target,{})
    assert target.read_bytes()==b'keep';c.close()


def test_reject_incomplete_current_schema(tmp_path):
    import sqlite3
    path=tmp_path/'fake.sqlite3'
    db=sqlite3.connect(path)
    for statement in ['CREATE TABLE products(id,code)','CREATE TABLE sales(id)',
                      'CREATE TABLE purchases(id)','CREATE TABLE attachments(relative_path,removed_at)',
                      'PRAGMA user_version=29']:db.execute(statement)
    db.commit()
    with pytest.raises(BackupError,match='estructura'):create_backup(db,tmp_path/'fake.zip',{})
    db.close()
