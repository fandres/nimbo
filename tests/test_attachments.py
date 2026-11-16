from datetime import date
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.attachments import AttachmentsRepository
from mi_negocio.storage import StorageError


def test_copies_persist_separate_names_and_keep_original(tmp_path):
    cat=CatalogRepository(tmp_path/'data'/'db')
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    row=PurchasesRepository(cat.connection).create(PurchaseDraft(date(2026,1,12),'Proveedor','',(PurchaseLineInput(p.id,1,100),)),request_id='a')
    repo=AttachmentsRepository(cat.connection);source=tmp_path/'factura.pdf';source.write_bytes(b'%PDF-1.4 test')
    first=repo.add('purchase',row['id'],source);second=repo.add('purchase',row['id'],source)
    assert first['relative_path']!=second['relative_path']
    assert '2026/01/Compras' in first['relative_path']
    assert repo.path(first).read_bytes()==source.read_bytes()
    source.unlink()
    assert repo.path(second).exists()
    repo.remove(first['id']);assert len(repo.list('purchase',row['id']))==1
    assert repo.path(first).exists() # Recoverable local copy, removed from record.
    cat.close();cat=CatalogRepository(tmp_path/'data'/'db')
    assert len(AttachmentsRepository(cat.connection).list('purchase',row['id']))==1
    cat.close()


def test_rejects_missing_owner_or_unsupported_file(tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=AttachmentsRepository(cat.connection)
    source=tmp_path/'bad.exe';source.write_bytes(b'executable')
    with pytest.raises(StorageError):repo.add('purchase',999,source)
    assert repo.list('purchase',999)==[]
    cat.close()


def test_migration_and_failed_copy_leave_existing_data(tmp_path,monkeypatch):
    import sqlite3
    import mi_negocio.attachments as module
    path=tmp_path/'db';cat=CatalogRepository(path)
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    row=PurchasesRepository(cat.connection).create(PurchaseDraft(date(2026,1,12),'Proveedor','',(PurchaseLineInput(p.id,1,100),)),request_id='a')
    cat.connection.execute('DROP TABLE attachments');cat.connection.execute('PRAGMA user_version=18');cat.connection.commit();cat.close()
    original=module.migrate_attachments
    def fail(c):original(c);raise sqlite3.OperationalError('rollback')
    monkeypatch.setattr(module,'migrate_attachments',fail)
    with pytest.raises(StorageError):CatalogRepository(path)
    with sqlite3.connect(path) as c:assert c.execute('PRAGMA user_version').fetchone()[0]==18
    monkeypatch.setattr(module,'migrate_attachments',original)
    cat=CatalogRepository(path);repo=AttachmentsRepository(cat.connection)
    source=tmp_path/'a.pdf';source.write_bytes(b'%PDF-1.4')
    def bad_copy(*args):raise OSError('full')
    monkeypatch.setattr(module.shutil,'copyfileobj',bad_copy)
    with pytest.raises(StorageError):repo.add('purchase',row['id'],source)
    assert repo.list('purchase',row['id'])==[]
    assert not list(repo.root.rglob('*.pdf'))
    assert PurchasesRepository(cat.connection).get(row['id'])['total_cents']==100
    cat.close()


def test_attachment_dialog_adds_copies(qtbot,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from mi_negocio.ui.attachments_dialog import AttachmentsDialog
    cat=CatalogRepository(tmp_path/'db')
    p=cat.create(validate_product(ProductInput('1','Máquina','product','1')))
    row=PurchasesRepository(cat.connection).create(PurchaseDraft(date(2026,1,12),'Proveedor','',(PurchaseLineInput(p.id,1,100),)),request_id='a')
    source=tmp_path/'invoice.pdf';source.write_bytes(b'%PDF-1.4')
    d=AttachmentsDialog(cat.connection,'purchase',row['id']);qtbot.addWidget(d)
    monkeypatch.setattr(QFileDialog,'getOpenFileNames',lambda *args:([str(source)],''))
    d.add();assert d.files.count()==1 and d.files.item(0).text()=='invoice.pdf'
    source.unlink();assert d.repo.path(d.repo.list('purchase',row['id'])[0]).exists()
    cat.close()
