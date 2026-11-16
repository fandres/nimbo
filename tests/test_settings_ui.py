from decimal import Decimal
from PySide6.QtCore import Qt
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.ui.settings_page import SettingsPage


def test_edit_payment_method(qtbot,tmp_path):
    repo=CatalogRepository(tmp_path/'db'); settings=SettingsRepository(repo.connection)
    page=SettingsPage(settings);qtbot.addWidget(page);page.show()
    editor=page.method_editor
    editor.table.selectRow(2)
    editor.rate.setText('2,125')
    qtbot.mouseClick(editor.save,Qt.LeftButton)
    assert settings.list_methods()[2].rate_percent==Decimal('2.125')
    editor.enabled.setChecked(False)
    qtbot.mouseClick(editor.save,Qt.LeftButton)
    assert len(settings.list_methods())==3
    page.close();repo.close()


def test_carrier_editor_adds_and_disables(qtbot,tmp_path):
    from mi_negocio.ui.carriers_editor import CarriersEditor
    repo=CatalogRepository(tmp_path/'db');settings=SettingsRepository(repo.connection)
    editor=CarriersEditor(settings);qtbot.addWidget(editor);editor.name.setText('Transportes del taller');editor.persist()
    key=editor.key
    assert any(row['name']=='Transportes del taller' for row in settings.list_carriers())
    editor.enabled.setChecked(False);editor.persist()
    assert key not in [row['id'] for row in settings.list_carriers()]
    repo.close()
