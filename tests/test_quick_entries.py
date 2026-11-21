from datetime import date
import pytest
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.quick_entries import QuickEntriesRepository

@pytest.fixture
def setup(tmp_path):
    cat=CatalogRepository(tmp_path/'db')
    cat.create(validate_product(ProductInput('P1','Producto','product','100')))
    yield cat,QuickEntriesRepository(cat.connection)
    cat.close()

def sale():
    return dict(date=date.today().isoformat(),customer='Cliente',product='P1',quantity='2',amount='100',method='Efectivo',account='Caja',paid='No',vat='No aplica',rate='19',withholding='No')

def test_incomplete_persists_without_financial_effects(setup):
    cat,repo=setup
    result=repo.save('sales',{'customer':'Ana','amount':'150'})
    assert result['operation_id'] is None
    assert result['error']
    assert repo.pending('sales')[0]['payload']['customer']=='Ana'
    assert cat.connection.execute('SELECT COUNT(*) FROM sales').fetchone()[0]==0
    assert not repo.include_provisional()

def test_complete_and_retry_do_not_duplicate(setup):
    cat,repo=setup
    data=sale()
    data['account']=cat.connection.execute('SELECT name FROM accounts WHERE id=1').fetchone()[0]
    saved=repo.save('sales',data)
    assert saved['operation_id'],saved['error']
    again=repo.save('sales',data,saved['id'],saved['revision'])
    assert again['operation_id']==saved['operation_id']
    assert not repo.pending('sales')
    assert cat.connection.execute('SELECT COUNT(*) FROM sales').fetchone()[0]==1

def test_expense_complete_and_pending(setup):
    cat,repo=setup
    category=cat.connection.execute('SELECT name FROM expense_categories LIMIT 1').fetchone()[0]
    draft=repo.save('expenses',{'concept':'Transporte','amount':'50'})
    completed=repo.save('expenses',dict(draft['payload'],category=category,date=date.today().isoformat(),paid='No'),draft['id'],draft['revision'])
    assert completed['operation_id'],completed['error']
    assert cat.connection.execute('SELECT COUNT(*) FROM expenses').fetchone()[0]==1

def test_stale_edit_rejected(setup):
    _,repo=setup
    a=repo.save('sales',{'customer':'A'})
    repo.save('sales',{'customer':'B'},a['id'],a['revision'])
    from mi_negocio.storage import StorageError
    with pytest.raises(StorageError):repo.save('sales',{'customer':'C'},a['id'],a['revision'])

def test_provisional_report_is_opt_in_filtered_and_not_double_counted(setup):
    from mi_negocio.ui.quick_entries_report import provisional_section
    cat,repo=setup
    data=sale();data['customer']='';data['account']=cat.connection.execute('SELECT name FROM accounts WHERE id=1').fetchone()[0]
    saved=repo.save('sales',data)
    today=date.today()
    assert provisional_section(cat.connection,'sales',today,today)==''
    repo.set_include_provisional(True)
    assert '200,00' in provisional_section(cat.connection,'sales',today,today)
    assert '200,00' not in provisional_section(cat.connection,'sales',today,today,account=999)
    assert provisional_section(cat.connection,'sales',today,today,query='not found')==''
    completed=repo.save('sales',dict(data,customer='Ana'),saved['id'],saved['revision'])
    assert completed['operation_id'],completed['error']
    assert provisional_section(cat.connection,'sales',today,today)==''

def test_post_failure_rolls_back_financial_effects_but_saves_draft(setup,monkeypatch):
    from mi_negocio.sales_repository import SalesRepository
    from mi_negocio.storage import StorageError
    cat,repo=setup
    original=SalesRepository.create
    def fail(self,*args,**kwargs):
        original(self,*args,**kwargs)
        raise StorageError('Fallo controlado después de crear')
    monkeypatch.setattr(SalesRepository,'create',fail)
    data=sale();data['account']=cat.connection.execute('SELECT name FROM accounts WHERE id=1').fetchone()[0]
    row=repo.save('sales',data)
    assert row['operation_id'] is None
    assert 'Fallo controlado' in row['error']
    assert cat.connection.execute('SELECT COUNT(*) FROM sales').fetchone()[0]==0


def test_quick_dialog_paste_save_reopen(qtbot,setup):
    from PySide6.QtWidgets import QApplication
    from mi_negocio.ui.quick_entry_dialog import QuickEntryDialog
    cat,repo=setup
    dialog=QuickEntryDialog(cat.connection,'sales');qtbot.addWidget(dialog)
    dialog.table.setCurrentCell(0,0)
    QApplication.clipboard().setText('19/11/2026\tAna\n19/11/2026\tLuis')
    dialog.paste();dialog.persist()
    assert len(repo.pending('sales'))==2
    assert all('Pendiente de completar' in dialog.table.item(i,len(dialog.fields)).text() for i in range(2))
    dialog.reject()
    reopened=QuickEntryDialog(cat.connection,'sales');qtbot.addWidget(reopened)
    assert reopened.table.rowCount()==3
    assert {reopened.table.item(i,1).text() for i in range(2)}=={'Ana','Luis'}
    reopened.reject()

def test_posted_row_rejects_concurrent_changed_payload(setup):
    from mi_negocio.storage import StorageError
    cat,repo=setup
    data=sale();data['account']=cat.connection.execute('SELECT name FROM accounts WHERE id=1').fetchone()[0]
    draft=repo.save('sales',dict(data,customer=''))
    repo.save('sales',data,draft['id'],draft['revision'])
    with pytest.raises(StorageError):repo.save('sales',dict(data,customer='Otro'),draft['id'],draft['revision'])

def test_unpaid_with_payment_date_stays_pending(setup):
    cat,repo=setup
    data=sale();data['account']=cat.connection.execute('SELECT name FROM accounts WHERE id=1').fetchone()[0]
    row=repo.save('sales',dict(data,paid_on=date.today().isoformat()))
    assert row['operation_id'] is None
    assert 'fecha' in row['error'].lower()

def test_ui_only_saves_edited_rows_and_continues_after_conflict(qtbot,setup):
    from mi_negocio.ui.quick_entry_dialog import QuickEntryDialog
    cat,repo=setup
    a=repo.save('sales',{'customer':'A'})
    dialog=QuickEntryDialog(cat.connection,'sales');qtbot.addWidget(dialog)
    dialog.persist()
    assert repo.get(a['id'])['revision']==a['revision']
    repo.save('sales',{'customer':'Otro'},a['id'],a['revision'])
    dialog.table.item(0,1).setText('Conflicto')
    dialog.table.item(1,1).setText('Fila independiente')
    dialog.persist()
    assert any(r['payload'].get('customer')=='Fila independiente' for r in repo.pending('sales'))
    assert dialog.dirty
    dialog.dirty=False;dialog.reject()

def test_backup_v28_still_validates_full_schema(tmp_path):
    from mi_negocio.backup_archive import create_backup,BackupError
    cat=CatalogRepository(tmp_path/'old'/'catalog.sqlite3')
    for table in ('quick_entries','quick_entry_settings','sale_revisions'):cat.connection.execute('DROP TABLE '+table)
    cat.connection.execute('PRAGMA user_version=28');cat.connection.commit()
    with pytest.raises(BackupError,match='estructura'):create_backup(cat.connection,tmp_path/'bad.zip',{})
    cat.close()


def test_pending_and_preference_survive_backup_and_reopen(tmp_path):
    from mi_negocio.backup_archive import create_backup,unpack_backup
    cat=CatalogRepository(tmp_path/'data'/'catalog.sqlite3');repo=QuickEntriesRepository(cat.connection)
    saved=repo.save('expenses',{'concept':'Pendiente','amount':'123,45'})
    repo.set_include_provisional(True)
    create_backup(cat.connection,tmp_path/'backup.zip',{});cat.close()
    unpack_backup(tmp_path/'backup.zip',tmp_path/'copy')
    restored=CatalogRepository(tmp_path/'copy'/'catalog.sqlite3');repo=QuickEntriesRepository(restored.connection)
    assert repo.include_provisional()
    assert repo.get(saved['id'])['payload']==saved['payload']
    assert len(repo.pending('expenses'))==1
    restored.close()

def test_ui_commits_active_cell_before_save(qtbot,setup):
    from PySide6.QtWidgets import QLineEdit
    from PySide6.QtCore import Qt
    from mi_negocio.ui.quick_entry_dialog import QuickEntryDialog
    cat,repo=setup
    dialog=QuickEntryDialog(cat.connection,'expenses');qtbot.addWidget(dialog);dialog.show();qtbot.waitExposed(dialog)
    dialog.table.setCurrentCell(0,1);dialog.table.editItem(dialog.table.item(0,1))
    editor=dialog.table.findChild(QLineEdit)
    assert editor is not None
    qtbot.waitUntil(editor.hasFocus)
    editor.setText('Edición activa')
    qtbot.mouseClick(dialog.save_button,Qt.LeftButton)
    assert repo.pending('expenses')[0]['payload']['concept']=='Edición activa'
    dialog.reject()


def test_report_preview_updates_from_config(qtbot,setup):
    from mi_negocio.ui.reports_page import ReportsPage
    cat,repo=setup
    repo.save('expenses',{'date':date.today().isoformat(),'concept':'Solo provisional','amount':'123'})
    page=ReportsPage(cat.connection);qtbot.addWidget(page);panel=page.panels[1]
    assert 'Solo provisional' not in panel.html
    repo.set_include_provisional(True);panel.refresh()
    assert 'Solo provisional' in panel.html
    assert 'Pendientes provisionales' in panel.html
    assert not panel.rows
    panel.search.setText('no coincide');assert 'Solo provisional' not in panel.html


def test_real_v28_migration_keeps_business_data(tmp_path):
    cat=CatalogRepository(tmp_path/'db')
    cat.create(validate_product(ProductInput('X','Conservado','product','100')))
    cat.connection.execute('DROP TABLE quick_entries');cat.connection.execute('DROP TABLE quick_entry_settings')
    cat.connection.execute('PRAGMA user_version=28');cat.connection.commit();cat.close()
    cat=CatalogRepository(tmp_path/'db')
    assert cat.list_products()[0].name=='Conservado'
    assert not QuickEntriesRepository(cat.connection).pending('sales')
    assert not QuickEntriesRepository(cat.connection).include_provisional()
    cat.close()
