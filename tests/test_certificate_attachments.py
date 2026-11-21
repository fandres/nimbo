from datetime import date
import pytest
from test_retention_certificates import setup
from mi_negocio.attachments import AttachmentsRepository
from mi_negocio.storage import StorageError


def test_certificate_copies_isolated_and_restored(tmp_path):
    from mi_negocio.backup_archive import create_backup,unpack_backup
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.retention_certificates import RetentionCertificatesRepository
    cat,sales,repo,add=setup(tmp_path);add();add(customer_identification='900-2');add(sold_on=date(2025,1,1))
    key=repo.document_owner(2026,'id:900-1')
    assert repo.document_owner(2026,'id:900-1')==key
    assert repo.document_owner(2025,'id:900-1')!=key
    other=repo.document_owner(2026,'id:900-2');assert other!=key
    source=tmp_path/'certificado.PDF';source.write_bytes(b'%PDF-support')
    attachments=AttachmentsRepository(cat.connection)
    row=attachments.add('retention_certificate',key,source)
    assert attachments.path(row).read_bytes()==source.read_bytes()
    assert row['relative_path'].startswith(f'2026/Retenciones/cliente-{key}/')
    assert not attachments.list('retention_certificate',other)
    assert repo.list(date(2026,1,1),date(2026,12,31))[0]['status']=='pending'
    with pytest.raises(StorageError):attachments.add('retention_certificate',key,tmp_path/'file.xml')
    create_backup(cat.connection,tmp_path/'copy.zip',{})
    unpack_backup(tmp_path/'copy.zip',tmp_path/'restore')
    restored=CatalogRepository(tmp_path/'restore'/'catalog.sqlite3')
    new=RetentionCertificatesRepository(restored.connection)
    assert new.document_owner(2026,'id:900-1')==key
    restored_files=AttachmentsRepository(restored.connection)
    assert restored_files.path(restored_files.list('retention_certificate',key)[0]).read_bytes()==source.read_bytes()
    attachments.remove(row['id']);assert not attachments.list('retention_certificate',key)
    assert source.exists() and attachments.path(row).exists()
    restored.close();cat.close()


def test_attach_offers_received_and_keeps_note(qtbot,tmp_path,monkeypatch):
    from mi_negocio.ui.retention_certificates_dialog import RetentionCertificatesDialog
    from mi_negocio.ui import attachments_dialog as files_ui
    from PySide6.QtWidgets import QMessageBox
    cat,sales,repo,add=setup(tmp_path);add()
    dialog=RetentionCertificatesDialog(repo,repo.list(date(2026,1,1),date(2026,12,31)))
    qtbot.addWidget(dialog)
    source=tmp_path/'soporte.png';source.write_bytes(b'image')
    monkeypatch.setattr(files_ui.QFileDialog,'getOpenFileNames',lambda *a:([str(source)],''))
    monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.No)
    files=dialog.documents(0);qtbot.addWidget(files);files.add()
    assert dialog.groups[0]['status']=='pending'
    assert dialog.document_buttons[0].text()=='1'
    dialog.table.cellWidget(0,4).setText('Nota conservada')
    monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.Yes)
    files.add()
    assert dialog.groups[0]['status']=='received' and dialog.groups[0]['note']=='Nota conservada'
    assert len(repo.history(2026,'id:900-1'))==1
    cat.close()


def test_failed_copy_does_not_offer_received(qtbot,tmp_path,monkeypatch):
    from mi_negocio.ui.retention_certificates_dialog import RetentionCertificatesDialog
    from mi_negocio.ui import attachments_dialog as files_ui
    cat,sales,repo,add=setup(tmp_path);add()
    dialog=RetentionCertificatesDialog(repo,repo.list(date(2026,1,1),date(2026,12,31)));qtbot.addWidget(dialog)
    monkeypatch.setattr(files_ui.QFileDialog,'getOpenFileNames',lambda *a:([str(tmp_path/'missing.pdf')],''))
    prompts=[];monkeypatch.setattr(files_ui.QMessageBox,'question',lambda *a:prompts.append(a))
    files=dialog.documents(0);qtbot.addWidget(files);files.add()
    assert files.error.text() and not prompts
    assert dialog.groups[0]['status']=='pending' and not repo.history(2026,'id:900-1')
    cat.close()


def test_stale_state_preserves_copy_and_other_update(qtbot,tmp_path,monkeypatch):
    from mi_negocio.ui.retention_certificates_dialog import RetentionCertificatesDialog
    from mi_negocio.ui import attachments_dialog as files_ui
    cat,sales,repo,add=setup(tmp_path);add()
    dialog=RetentionCertificatesDialog(repo,repo.list(date(2026,1,1),date(2026,12,31)));qtbot.addWidget(dialog)
    repo.save(2026,'id:900-1','requested','Otra actualización',expected_revision=0)
    source=tmp_path/'cert.pdf';source.write_bytes(b'%PDF-test')
    monkeypatch.setattr(files_ui.QFileDialog,'getOpenFileNames',lambda *a:([str(source)],''))
    monkeypatch.setattr(files_ui.QMessageBox,'question',lambda *a:files_ui.QMessageBox.Yes)
    files=dialog.documents(0);qtbot.addWidget(files);files.add()
    assert dialog.error.text()
    assert files.files.count()==1
    assert repo.list(date(2026,1,1),date(2026,12,31))[0]['status']=='requested'
    cat.close()


def test_certificate_documents_migration_rolls_back(tmp_path,monkeypatch):
    import sqlite3
    from mi_negocio.repository import CatalogRepository
    import mi_negocio.retention_certificates as module
    cat,sales,repo,add=setup(tmp_path);add()
    cat.connection.execute('DROP TABLE retention_certificate_documents')
    cat.connection.execute('PRAGMA user_version=27');cat.connection.commit();cat.close()
    original=module.migrate_certificate_documents
    def fail(c):original(c);raise sqlite3.OperationalError('failure')
    monkeypatch.setattr(module,'migrate_certificate_documents',fail)
    with pytest.raises(StorageError):CatalogRepository(tmp_path/'db')
    with sqlite3.connect(tmp_path/'db') as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==27
        assert not c.execute("SELECT name FROM sqlite_master WHERE name='retention_certificate_documents'").fetchone()
    monkeypatch.setattr(module,'migrate_certificate_documents',original)
    cat=CatalogRepository(tmp_path/'db')
    assert cat.connection.execute('PRAGMA user_version').fetchone()[0]==29
    cat.close()
