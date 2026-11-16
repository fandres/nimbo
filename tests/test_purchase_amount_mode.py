from datetime import date
from decimal import Decimal
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import PurchaseDraft, calculate_purchase_totals
from mi_negocio.purchases_repository import PurchasesRepository, draft_from_record
from mi_negocio.ui.purchase_line_editor import PurchaseLineDialog


def test_total_default_exact_roundtrip_and_unit_mode(qtbot, tmp_path):
    cat = CatalogRepository(tmp_path/'db')
    product = cat.create(validate_product(ProductInput('001', 'Máquina', 'product', '100')))
    d = PurchaseLineDialog([product]); qtbot.addWidget(d)
    assert d.total_mode.isChecked() and not d.unit_mode.isChecked()
    d.product.setCurrentIndex(0); d.quantity.setValue(3); d.amount.setText('100')
    d.accept_line()
    draft = PurchaseDraft(date.today(), 'Proveedor', '', (d.result_line,))
    assert calculate_purchase_totals(draft).merchandise_cents == 10000
    repo = PurchasesRepository(cat.connection)
    saved = repo.create(draft, request_id='total')
    restored = draft_from_record(saved)
    assert calculate_purchase_totals(restored).merchandise_cents == 10000
    edit = PurchaseLineDialog([product], restored.lines[0]); qtbot.addWidget(edit)
    assert edit.amount.text() == '100,00'
    edit.unit_mode.click(); edit.amount.setText('42,50'); edit.accept_line()
    assert calculate_purchase_totals(PurchaseDraft(date.today(), 'Proveedor', '', (edit.result_line,))).merchandise_cents == 12750
    cat.close()


def test_usd_total_and_switch_preserves_exact_total(qtbot, tmp_path):
    cat = CatalogRepository(tmp_path/'db')
    product = cat.create(validate_product(ProductInput('001', 'Máquina', 'product', '100')))
    d = PurchaseLineDialog([product]); qtbot.addWidget(d)
    d.product.setCurrentIndex(0); d.quantity.setValue(3); d.amount.setText('100')
    d.unit_mode.click(); d.total_mode.click()
    assert d.amount.text() == '100,00'
    d.exchange.set_values('USD', Decimal('4000'), date.today())
    d.accept_line()
    draft = PurchaseDraft(date.today(), 'Proveedor', '', (d.result_line,))
    assert calculate_purchase_totals(draft).merchandise_cents == 40000000
    cat.close()


def test_quantity_changes_follow_selected_mode(qtbot):
    d = PurchaseLineDialog([]); qtbot.addWidget(d)
    d.amount.setText('100'); d.quantity.setValue(2)
    assert d.original_total() == 10000
    d.unit_mode.click()
    assert d.amount.text() == '50,00'
    d.quantity.setValue(3)
    assert d.original_total() == 15000
    d.total_mode.click()
    assert d.amount.text() == '150,00'


def test_migrate_14_keeps_historical_unit_prices(tmp_path, monkeypatch):
    import sqlite3
    import pytest
    from mi_negocio import database
    from mi_negocio.storage import StorageError
    path = tmp_path/'old'
    cat = CatalogRepository(path)
    product = cat.create(validate_product(ProductInput('001', 'Máquina', 'product', '100')))
    from mi_negocio.purchases import PurchaseLineInput
    draft = PurchaseDraft(date.today(), 'Proveedor', '', (PurchaseLineInput(product.id, 3, 4250),))
    saved = PurchasesRepository(cat.connection).create(draft, request_id='old')
    cat.connection.execute('ALTER TABLE purchase_lines DROP COLUMN total_cost_cents')
    cat.connection.execute('PRAGMA user_version=14'); cat.connection.commit(); cat.close()
    original = database.migrate_purchase_totals
    def fail(c):
        original(c)
        raise sqlite3.OperationalError('test rollback')
    monkeypatch.setattr(database, 'migrate_purchase_totals', fail)
    with pytest.raises(StorageError): CatalogRepository(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0] == 14
        assert 'total_cost_cents' not in {r[1] for r in c.execute('PRAGMA table_info(purchase_lines)')}
    monkeypatch.setattr(database, 'migrate_purchase_totals', original)
    cat = CatalogRepository(path)
    row = PurchasesRepository(cat.connection).get(saved['id'])
    assert row['lines'][0]['total_cost_cents'] is None
    assert calculate_purchase_totals(draft_from_record(row)).merchandise_cents == 12750
    assert list(tmp_path.glob('*.backup-*'))
    cat.close()
