import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.ui.catalog_page import CatalogPage


@pytest.fixture
def window(qtbot, tmp_path):
    repo = CatalogRepository(tmp_path / 'ui.sqlite3')
    widget = CatalogPage(repo)
    widget.resize(1144, 720)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.close()
    repo.close()


def enter(window, qtbot, code='010', name='Impresora', price='1500,25', service=False):
    qtbot.mouseClick(window.new_button, Qt.LeftButton)
    dialog = window.dialog
    dialog.code.setText(code)
    dialog.name.setText(name)
    dialog.price.setText(price)
    if service:
        dialog.kind.setCurrentIndex(1)
    return dialog


def save(dialog, qtbot):
    qtbot.mouseClick(dialog.save_button, Qt.LeftButton)


def test_create_edit_and_exact_display(window, qtbot):
    dialog = enter(window, qtbot)
    save(dialog, qtbot)
    assert not dialog.isVisible()
    assert window.table.item(0, 0).text() == '010'
    assert window.table.item(0, 3).text() == '$ 1.500,25'
    window.table.selectRow(0)
    qtbot.mouseClick(window.edit_button, Qt.LeftButton)
    window.dialog.name.setText('Impresora nueva')
    save(window.dialog, qtbot)
    assert window.repository.list_products()[0].name == 'Impresora nueva'


def test_duplicate_preserves_form_and_cancel_does_not_write(window, qtbot):
    save(enter(window, qtbot), qtbot)
    dialog = enter(window, qtbot, name='Otro producto')
    save(dialog, qtbot)
    assert dialog.isVisible()
    assert dialog.code.text() == '010'
    assert dialog.name.text() == 'Otro producto'
    assert dialog.errors['code'].text()
    qtbot.mouseClick(dialog.cancel_button, Qt.LeftButton)
    assert len(window.repository.list_products()) == 1


def test_zero_service_and_filters(window, qtbot):
    save(enter(window, qtbot, 'S01', 'Diseño', '0', True), qtbot)
    save(enter(window, qtbot), qtbot)
    window.kind_filter.setCurrentIndex(2)
    window.search.setText('DISEÑO')
    assert window.table.rowCount() == 1
    assert window.table.item(0, 0).text() == 'S01'
    window.search.setText('ausente')
    assert window.table.rowCount() == 0
    assert window.empty_label.isVisible()
    assert not window.edit_button.isEnabled()
    qtbot.mouseClick(window.clear_button, Qt.LeftButton)
    assert window.table.rowCount() == 2


def test_invalid_price_does_not_save(window, qtbot):
    dialog = enter(window, qtbot, price='-5')
    save(dialog, qtbot)
    assert dialog.errors['price'].text()
    assert window.repository.list_products() == []


def test_deactivate_confirmation_and_hidden_save(window, qtbot):
    save(enter(window, qtbot), qtbot)
    window.table.selectRow(0)

    def confirm():
        box = QApplication.activeModalWidget()
        assert isinstance(box, QMessageBox)
        box.button(QMessageBox.Yes).click()

    QTimer.singleShot(0, confirm)
    qtbot.mouseClick(window.active_button, Qt.LeftButton)
    assert window.repository.list_products()[0].active is False
    window.active_filter.setCurrentIndex(2)
    window.table.selectRow(0)
    qtbot.mouseClick(window.active_button, Qt.LeftButton)
    assert window.table.rowCount() == 0
    assert window.repository.list_products()[0].active is True
    assert window.notice.text()


def test_save_outside_current_filter_shows_success(window, qtbot):
    window.search.setText('no coincide')
    save(enter(window, qtbot), qtbot)
    assert window.table.rowCount() == 0
    assert len(window.repository.list_products()) == 1
    assert 'filtro' in window.notice.text().lower()


def test_storage_failure_keeps_unsaved_input(window, qtbot, tmp_path):
    import sqlite3
    dialog = enter(window, qtbot)
    connection = sqlite3.connect(tmp_path / 'ui.sqlite3')
    connection.execute('BEGIN EXCLUSIVE')
    try:
        save(dialog, qtbot)
        assert dialog.isVisible()
        assert dialog.name.text() == 'Impresora'
        assert dialog.general_error.text()
    finally:
        connection.rollback()
        connection.close()
    assert window.repository.list_products() == []


def test_recovered_refresh_clears_old_storage_error(window, qtbot, tmp_path):
    import sqlite3
    save(enter(window, qtbot), qtbot)
    connection = sqlite3.connect(tmp_path / 'ui.sqlite3')
    connection.execute('BEGIN EXCLUSIVE')
    try:
        window.search.setText('010')
        assert 'No se pudo' in window.notice.text()
    finally:
        connection.rollback()
        connection.close()
    window.search.clear()
    assert window.table.rowCount() == 1
    assert not window.notice.text()


def test_validation_keeps_buttons_inside_small_dialog(window, qtbot):
    dialog = enter(window, qtbot, code='', name='', price='')
    dialog.resize(460, 533)
    save(dialog, qtbot)
    QApplication.processEvents()
    assert dialog.errors['code'].text()
    assert dialog.height() <= 560
    assert dialog.save_button.mapTo(dialog, dialog.save_button.rect().bottomRight()).y() < dialog.height()


def test_new_classifications_reused_filtered_and_edited(window, qtbot):
    dialog = enter(window, qtbot)
    dialog.brand.setEditText('Bambu Lab')
    dialog.subtype.setEditText('Impresora 3D')
    save(dialog, qtbot)
    assert window.repository.list_products()[0].brand == 'Bambu Lab'
    dialog = enter(window, qtbot, code='020')
    assert dialog.brand.findText('Bambu Lab') >= 0
    dialog.brand.setEditText('Otro')
    dialog.subtype.setEditText('Láser')
    save(dialog, qtbot)
    window.brand_filter.setCurrentText('Bambu Lab')
    window.subtype_filter.setCurrentText('Impresora 3D')
    assert window.table.rowCount() == 1
    window.table.selectRow(0)
    qtbot.mouseClick(window.edit_button, Qt.LeftButton)
    assert window.dialog.brand.currentText() == 'Bambu Lab'
    assert window.dialog.subtype.currentText() == 'Impresora 3D'
    window.dialog.subtype.setEditText('')
    save(window.dialog, qtbot)
    assert window.table.rowCount() == 0
    window._clear_filters()
    assert window.table.rowCount() == 2


def test_cancel_does_not_create_classification(window, qtbot):
    dialog = enter(window, qtbot)
    dialog.brand.setEditText('No guardar')
    qtbot.mouseClick(dialog.cancel_button, Qt.LeftButton)
    assert window.repository.list_options('brand') == []


def test_manage_lists_create_rename_and_preserve_filter(window, qtbot):
    dialog = enter(window, qtbot)
    dialog.brand.setEditText('Marca inicial')
    save(dialog, qtbot)
    window.brand_filter.setCurrentText('Marca inicial')
    qtbot.mouseClick(window.lists_button, Qt.LeftButton)
    manager = window.lists_dialog
    manager.options.setCurrentRow(0)
    manager.name.setText('Marca corregida')
    qtbot.mouseClick(manager.rename_button, Qt.LeftButton)
    assert window.repository.list_products()[0].brand == 'Marca corregida'
    manager.group.setCurrentIndex(1)
    manager.name.setText('Láser de fibra')
    qtbot.mouseClick(manager.add_button, Qt.LeftButton)
    assert window.repository.list_options('subtype') == ['Láser de fibra']
    manager.close()
    assert window.brand_filter.currentText() == 'Marca corregida'
    assert window.table.rowCount() == 1


def test_lists_enter_renames_selected_option(window, qtbot):
    window.repository.add_option('brand', 'Original')
    window._manage_lists()
    manager = window.lists_dialog
    manager.options.setCurrentRow(0)
    manager.name.setText('Corregida')
    manager.name.setFocus()
    qtbot.keyClick(manager.name, Qt.Key_Return)
    assert window.repository.list_options('brand') == ['Corregida']


def test_small_window_has_space_for_full_product_row(window, qtbot):
    save(enter(window, qtbot), qtbot)
    window.resize(800, 560)
    QApplication.processEvents()
    assert window.table.viewport().height() >= window.table.rowHeight(0)


def test_product_form_shows_all_fields_without_scrolling(window, qtbot):
    from PySide6.QtWidgets import QScrollArea
    dialog = enter(window, qtbot)
    QApplication.processEvents()
    scroll = dialog.findChild(QScrollArea)
    assert dialog.width() > dialog.height()
    assert scroll.verticalScrollBar().maximum() == 0
    for field in (dialog.code, dialog.name, dialog.kind, dialog.subtype, dialog.brand, dialog.price, dialog.active):
        assert scroll.viewport().rect().contains(field.mapTo(scroll.viewport(), field.rect().center()))


@pytest.mark.parametrize("leave_by", ["tab", "click"])
def test_duplicate_code_warns_when_leaving_field(window, qtbot, leave_by):
    product = window.repository.create(validate_product(ProductInput('010', 'Existente', 'product', '100', False)))
    window._new()
    dialog = window.dialog
    qtbot.waitUntil(dialog.isVisible)
    qtbot.wait(20)
    dialog.code.setFocus()
    dialog.code.setText('010')
    if leave_by == 'tab':
        qtbot.keyClick(dialog.code, Qt.Key_Tab)
    else:
        qtbot.mouseClick(dialog.name, Qt.LeftButton)
    qtbot.waitUntil(lambda: dialog.errors['code'].isVisible())
    assert dialog.code.property('invalid')
    assert dialog.code.hasFocus()
    assert dialog.name.text() == ''
    assert len(window.repository.list_products()) == 1
    dialog.code.setText('011')
    assert not dialog.errors['code'].isVisible()
    qtbot.keyClick(dialog.code, Qt.Key_Tab)
    assert not dialog.code.property('invalid')
    dialog.reject()
    window._open_dialog(product)
    edit = window.dialog
    qtbot.waitUntil(edit.isVisible)
    qtbot.wait(20)
    edit.code.setFocus()
    qtbot.keyClick(edit.code, Qt.Key_Tab)
    assert not edit.errors['code'].isVisible()
    edit.reject()
