from dataclasses import replace
from datetime import date
import pytest
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.sales import SaleDraft,SaleLineInput
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.retention_certificates import RetentionCertificatesRepository
from mi_negocio.storage import StorageError


def setup(tmp_path):
    cat=CatalogRepository(tmp_path/'db');sales=SalesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('P','Máquina','product','100')))
    method=SettingsRepository(cat.connection).list_methods()[0]
    draft=SaleDraft(date(2026,1,1),'FE-1',(SaleLineInput(p.id,1,100000),),method.id,1,
                    customer_name='Empresa & Uno',customer_identification='900-1',customer_email='uno@example.com',has_withholding=True)
    def add(**kwargs):
        d=replace(draft,**kwargs)
        return sales.create(d,request_id=str(len(sales.list_sales()))+str(kwargs),expected_method=method)
    return cat,sales,RetentionCertificatesRepository(cat.connection),add


def test_groups_year_document_and_filters(tmp_path):
    cat,sales,repo,add=setup(tmp_path)
    add();add(invoice_ref='FE-2',customer_name='Empresa renombrada',sold_on=date(2026,2,1))
    add(sold_on=date(2025,2,1));add(customer_identification='900-2')
    add(has_withholding=False)
    cancelled=add(customer_identification='Anulada');sales.cancel(cancelled['id'],'Prueba')
    groups=repo.list(date(2026,1,1),date(2026,12,31))
    assert len(groups)==2
    g=next(g for g in groups if g['identification']=='900-1')
    assert len(g['sales'])==2 and g['withholding_cents']==5000
    assert len(repo.list(date(2026,1,1),date(2026,12,31),query='900-1'))==1
    assert len(repo.list(date(2026,1,1),date(2026,12,31),query='uno@example.com'))==2
    assert all(s['has_withholding'] and not s['cancelled_at'] for g in groups for s in g['sales'])
    with pytest.raises(StorageError):repo.list(date(2026,2,1),date(2026,1,1))
    cat.close()


def test_annual_state_history_and_amounts_unchanged(tmp_path):
    cat,sales,repo,add=setup(tmp_path);sale=add();add(sold_on=date(2026,2,1));add(sold_on=date(2025,1,1))
    g=repo.list(date(2026,1,1),date(2026,1,31))[0]
    repo.save(g['year'],g['customer_key'],'requested','Solicitado por correo',expected_revision=0)
    feb=repo.list(date(2026,2,1),date(2026,2,28))[0]
    assert feb['status']=='requested' and feb['revision']==1
    repo.save(g['year'],g['customer_key'],'received','Certificado recibido',expected_revision=1)
    assert len(repo.history(g['year'],g['customer_key']))==2
    assert repo.list(date(2025,1,1),date(2025,12,31))[0]['status']=='pending'
    assert repo.list(date(2026,1,1),date(2026,12,31),status='requested')==[]
    assert sales.get(sale['id'])['total_cents']==sale['total_cents']
    with pytest.raises(StorageError):repo.save(g['year'],g['customer_key'],'pending','',expected_revision=1)
    with pytest.raises(StorageError):repo.save(g['year'],g['customer_key'],'bad','',expected_revision=2)
    cat.close()


def test_missing_id_group_and_reopen(tmp_path):
    cat,sales,repo,add=setup(tmp_path)
    add(customer_identification='',customer_name='  Cliente Uno  ')
    add(customer_identification='',customer_name='cliente uno')
    g=repo.list(date(2026,1,1),date(2026,12,31))[0]
    assert g['missing_identification'] and len(g['sales'])==2
    repo.save(g['year'],g['customer_key'],'requested','Nota',expected_revision=0)
    cat.close();cat=CatalogRepository(tmp_path/'db');repo=RetentionCertificatesRepository(cat.connection)
    assert repo.list(date(2026,1,1),date(2026,12,31))[0]['status']=='requested'
    cat.close()


def test_report_and_workflow_ui(qtbot,tmp_path,monkeypatch):
    from mi_negocio.ui.reports_page import ReportPanel
    from PySide6.QtCore import QDate
    cat,sales,repo,add=setup(tmp_path);add()
    panel=ReportPanel('retentions',cat.connection);qtbot.addWidget(panel)
    panel.start.setDate(QDate(2026,1,1));panel.end.setDate(QDate(2026,12,31))
    assert len(panel.rows)==1
    assert 'Empresa &amp; Uno' in panel.html and 'uno@example.com' in panel.html
    assert 'FE-1' in panel.html and '$ 25,00' in panel.html
    dialog=panel.manage_certificates();qtbot.addWidget(dialog)
    combo=dialog.table.cellWidget(0,3)
    combo.setCurrentIndex(combo.findData('requested'));combo.activated.emit(combo.currentIndex())
    assert repo.list(date(2026,1,1),date(2026,12,31))[0]['status']=='requested'
    dialog.accept();panel.refresh()
    assert 'Solicitado' in panel.html
    panel.certificate_status.setCurrentIndex(panel.certificate_status.findData('received'))
    assert not panel.rows and 'Sin retenciones' in panel.html
    cat.close()


def test_full_year_selector_and_historical_totals(qtbot,tmp_path):
    from mi_negocio.ui.reports_page import ReportPanel
    cat,sales,repo,add=setup(tmp_path);row=add(sold_on=date(2025,1,1))
    cat.connection.execute('UPDATE sales SET withholding_deducted=0 WHERE id=?',(row['id'],));cat.connection.commit()
    panel=ReportPanel('retentions',cat.connection);qtbot.addWidget(panel)
    assert panel.month.currentData()==0
    panel.year.setCurrentIndex(panel.year.findData(2025))
    assert panel.start.date().toPython()==date(2025,1,1)
    assert panel.end.date().toPython()==date(2025,12,31)
    assert panel.rows[0]['informative_cents']==2500
    assert panel.rows[0]['booked_cents']==0
    assert 'Informativa histórica' in panel.html
    cat.close()


def test_migration_rollback_then_restore_certificate_backup(tmp_path,monkeypatch):
    import sqlite3
    import mi_negocio.retention_certificates as module
    from mi_negocio.backup_archive import create_backup,unpack_backup
    cat,sales,repo,add=setup(tmp_path);add()
    for name in ('retention_certificates','retention_certificate_events'):cat.connection.execute('DROP TABLE '+name)
    cat.connection.execute('PRAGMA user_version=26');cat.connection.commit();cat.close()
    original=module.migrate_certificates
    def fail(c):original(c);raise sqlite3.OperationalError('failure')
    monkeypatch.setattr(module,'migrate_certificates',fail)
    with pytest.raises(StorageError):CatalogRepository(tmp_path/'db')
    with sqlite3.connect(tmp_path/'db') as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==26
        assert not c.execute("SELECT name FROM sqlite_master WHERE name='retention_certificates'").fetchone()
    monkeypatch.setattr(module,'migrate_certificates',original)
    cat=CatalogRepository(tmp_path/'db');repo=RetentionCertificatesRepository(cat.connection)
    g=repo.list(date(2026,1,1),date(2026,12,31))[0]
    repo.save(g['year'],g['customer_key'],'received','Documento recibido',expected_revision=0)
    create_backup(cat.connection,tmp_path/'backup.zip',{})
    unpack_backup(tmp_path/'backup.zip',tmp_path/'restored')
    restored=CatalogRepository(tmp_path/'restored'/'catalog.sqlite3')
    new=RetentionCertificatesRepository(restored.connection)
    assert new.list(date(2026,1,1),date(2026,12,31))[0]['status']=='received'
    assert len(new.history(g['year'],g['customer_key']))==1
    restored.close();cat.close()
