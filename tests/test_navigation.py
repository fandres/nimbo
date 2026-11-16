import sqlite3

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.ui.main_window import MainWindow


@pytest.fixture
def shell(qtbot, tmp_path):
    repo = CatalogRepository(tmp_path / 'navigation.sqlite3')
    window = MainWindow(repo)
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    yield window
    window.close()
    repo.close()


def create(repo, code, kind='product', active=True):
    return repo.create(validate_product(ProductInput(code, 'Ejemplo '+code, kind, '100', active)))


def test_starts_at_home_and_catalog_link_works(shell, qtbot):
    assert shell.pages.currentWidget() is shell.home_page
    qtbot.mouseClick(shell.home_page.catalog_button, Qt.LeftButton)
    assert shell.pages.currentWidget() is shell.catalog_page
    assert shell.nav_buttons['catalog'].isChecked()
    qtbot.mouseClick(shell.nav_buttons['home'], Qt.LeftButton)
    assert shell.pages.currentWidget() is shell.home_page


def test_navigation_preserves_catalog_selection_and_filters(shell, qtbot):
    page = shell.catalog_page
    create(page.repository, '010')
    shell.navigate('catalog')
    page.refresh_products()
    page.search.setText('010')
    page.kind_filter.setCurrentIndex(1)
    page.table.selectRow(0)
    selected_id = page._selected().id
    shell.navigate('home')
    shell.navigate('catalog')
    assert page.search.text() == '010'
    assert page.kind_filter.currentData() == 'product'
    assert page._selected().id == selected_id


def test_product_shortcut_is_scoped_to_catalog(shell, qtbot):
    qtbot.keyClick(shell, Qt.Key_N, Qt.ControlModifier)
    assert shell.catalog_page.dialog is None
    for _ in range(2):
        shell.navigate('catalog')
        shell.catalog_page.search.setFocus()
        qtbot.keyClick(shell.catalog_page.search, Qt.Key_N, Qt.ControlModifier)
        qtbot.waitUntil(lambda: shell.catalog_page.dialog is not None and shell.catalog_page.dialog.isVisible())
        dialog = shell.catalog_page.dialog
        dialog.reject()
        shell.navigate('home')
        shell.nav_buttons['home'].setFocus()
        qtbot.keyClick(shell.nav_buttons['home'], Qt.Key_N, Qt.ControlModifier)
        assert not dialog.isVisible()


def test_future_actions_disabled_and_no_invented_balance(shell):
    assert shell.nav_buttons['reports'].isEnabled()
    for action in shell.home_page.future_actions:
        assert not action.isEnabled()
    texts = '\n'.join(label.text() for label in shell.home_page.findChildren(QLabel))
    assert 'cuentas sin configurar' in texts
    assert shell.nav_buttons['money'].isEnabled()
    assert 'Aún no has registrado ventas.' in texts
    assert shell.nav_buttons['sales'].isEnabled()
    assert shell.nav_buttons['settings'].isEnabled()


def test_home_counts_refresh_and_exclude_inactive(shell):
    repo = shell.catalog_page.repository
    create(repo, '1')
    create(repo, '2')
    create(repo, '3', 'service')
    create(repo, '4', active=False)
    shell.navigate('home')
    assert shell.home_page.products_count.text() == '2'
    assert shell.home_page.services_count.text() == '1'
    repo.set_active(repo.list_products('1')[0].id, False)
    shell.navigate('catalog')
    shell.navigate('home')
    assert shell.home_page.products_count.text() == '1'


def test_storage_error_hides_stale_counts_and_can_retry(shell, qtbot, tmp_path):
    create(shell.catalog_page.repository, '1')
    shell.home_page.refresh_summary()
    connection = sqlite3.connect(tmp_path / 'navigation.sqlite3')
    connection.execute('BEGIN EXCLUSIVE')
    try:
        shell.home_page.refresh_summary()
        assert shell.home_page.products_count.text() == '—'
        assert shell.home_page.services_count.text() == '—'
        assert shell.home_page.error_label.text()
        assert shell.home_page.retry_button.isVisible()
    finally:
        connection.rollback()
        connection.close()
    qtbot.mouseClick(shell.home_page.retry_button, Qt.LeftButton)
    assert shell.home_page.products_count.text() == '1'
    assert not shell.home_page.error_label.text()


def test_small_home_has_no_horizontal_scroll_and_reaches_bottom(shell, qtbot):
    shell.resize(800, 560)
    QApplication.processEvents()
    scroll = shell.home_page.scroll
    assert scroll.horizontalScrollBar().maximum() == 0
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    QApplication.processEvents()
    assert scroll.viewport().rect().contains(shell.home_page.recent_sales.mapTo(scroll.viewport(), shell.home_page.recent_sales.rect().center()))
    shell.nav_buttons['catalog'].setFocus()
    qtbot.keyClick(shell.nav_buttons['catalog'], Qt.Key_Space)
    assert shell.pages.currentWidget() is shell.catalog_page


def test_home_date_has_literal_spanish_connector(shell):
    from PySide6.QtCore import QDate
    assert f' {QDate.currentDate().day()} de ' in shell.home_page.date_label.text()


def test_shortcut_after_sidebar_navigation_and_modal_suppression(shell, qtbot):
    from mi_negocio.ui.product_dialog import ProductDialog
    qtbot.mouseClick(shell.nav_buttons['catalog'], Qt.LeftButton)
    qtbot.keyClick(shell.nav_buttons['catalog'], Qt.Key_N, Qt.ControlModifier)
    qtbot.waitUntil(lambda: shell.catalog_page.dialog is not None and shell.catalog_page.dialog.isVisible())
    dialog = shell.catalog_page.dialog
    qtbot.keyClick(dialog.code, Qt.Key_N, Qt.ControlModifier)
    visible = [d for d in shell.findChildren(ProductDialog) if d.isVisible()]
    assert visible == [dialog]
    dialog.reject()


def test_wide_home_shows_all_sections_without_scrolling(shell):
    shell.resize(1320, 720)
    for _ in range(3):
        QApplication.processEvents()
    scroll = shell.home_page.scroll
    assert scroll.verticalScrollBar().maximum() == 0
    assert scroll.horizontalScrollBar().maximum() == 0


def test_sidebar_icons_and_titles_share_alignment(shell):
    shell.resize(1320, 720)
    QApplication.processEvents()
    positions = []
    for button in shell.nav_buttons.values():
        glyph = button.findChild(QLabel, 'navIcon')
        title = button.findChild(QLabel, 'navTitle')
        assert glyph is not None and title is not None
        assert glyph.geometry().bottom() < title.geometry().top()
        positions.append((glyph.geometry().center().x(), glyph.y(), title.y()))
    assert len(set(positions)) == 1
