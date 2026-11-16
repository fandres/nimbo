from datetime import date,timedelta
from pathlib import Path
from PySide6.QtCore import QSettings
from mi_negocio.backup_preferences import BackupPreferences
from mi_negocio.ui.backup_page import BackupPage
from mi_negocio.repository import CatalogRepository


def test_daily_backup_opt_in_and_portable_preferences(qtbot,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:None)
    prefs=BackupPreferences(QSettings(str(tmp_path/'prefs.ini'),QSettings.IniFormat))
    assert not prefs.enabled() and not prefs.due()
    prefs.configure(True,tmp_path/'copies');assert prefs.due()
    c=CatalogRepository(tmp_path/'data'/'catalog.sqlite3')
    page=BackupPage(c.connection,preferences=prefs);qtbot.addWidget(page)
    page.automatic_backup();assert len(list((tmp_path/'copies').glob('*.zip')))==1
    page.automatic_backup();assert len(list((tmp_path/'copies').glob('*.zip')))==1
    assert prefs.due(date.today()+timedelta(days=1))
    prefs.apply({'sales/vat_enabled_default':True})
    assert prefs.export()['sales/vat_enabled_default']
    assert prefs.enabled() and prefs.folder()==str(tmp_path/'copies')
    assert 'backup/folder' not in prefs.export()
    c.close()


def test_restore_blocks_unsaved_inline_account_changes(qtbot,tmp_path,monkeypatch):
    from mi_negocio.ui.settings_page import SettingsPage
    from mi_negocio.settings_repository import SettingsRepository
    from mi_negocio.ui.preferences import DisplayPreferences
    c=CatalogRepository(tmp_path/'db')
    prefs=DisplayPreferences(QSettings(str(tmp_path/'prefs.ini'),QSettings.IniFormat))
    settings=SettingsPage(SettingsRepository(c.connection),preferences=prefs);qtbot.addWidget(settings)
    assert not settings.backup_page.has_unsaved_changes()
    settings.account_editor.table.selectRow(0)
    settings.account_editor.name.setText('Mi cuenta modificada')
    assert settings.backup_page.has_unsaved_changes()
    settings.backup_page.restore_manual()
    assert 'sin guardar' in settings.backup_page.message.text()
    settings.account_editor.persist()
    assert not settings.backup_page.has_unsaved_changes()
    c.close()
