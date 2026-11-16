"""Release gate: inventory valuation survives a complete backup/restore cycle."""
from datetime import date
from dataclasses import replace
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.inventory_repository import InventoryRepository
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput, PurchaseCostInput
from mi_negocio.purchases_repository import PurchasesRepository, draft_from_record
from mi_negocio.purchase_receipts_repository import PurchaseReceiptsRepository
from mi_negocio.sales import SaleDraft, SaleLineInput, ReceiptInput
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.profitability_repository import ProfitabilityRepository
from mi_negocio.attachments import AttachmentsRepository
from mi_negocio.backup_archive import create_backup
from mi_negocio.backup_restore import prepare_restore, apply_restore


def test_purchase_sale_correction_backup_restore_preserves_values_and_documents(tmp_path):
    db = tmp_path/'data'/'catalog.sqlite3'
    cat = CatalogRepository(db)
    product = cat.create(validate_product(ProductInput('001', 'Máquina', 'product', '200')))
    inv = InventoryRepository(cat.connection)
    inv.initialize('receipts', {}, expected_token=inv.preview()['token'])
    purchases = PurchasesRepository(cat.connection)
    purchase = purchases.create(PurchaseDraft(date.today(), 'Proveedor', 'COMPRA-1',
        (PurchaseLineInput(product.id, 3, 10000),),
        costs=(PurchaseCostInput('international_shipping', '', 3000),),
        costs_complete=True), request_id='purchase')
    PurchaseReceiptsRepository(cat.connection).receive(purchase['id'], date.today(), expected_revision=purchase['revision'])
    method = SettingsRepository(cat.connection).list_methods()[0]
    sales = SalesRepository(cat.connection)
    sale = sales.create(SaleDraft(date.today(), 'VENTA-1', (SaleLineInput(product.id, 2, 20000),),
        method.id, 1, customer_name='Cliente'), request_id='sale', expected_method=method,
        receipt=ReceiptInput(date.today(), 1, 500))
    sales.save_detail(sale['id'], invoice_ref='VENTA-1', has_withholding=False, tracking_number='',
        lines=(SaleLineInput(product.id, 1, 20000),))
    purchase = purchases.get(purchase['id'])
    purchases.update(purchase['id'], replace(draft_from_record(purchase),
        costs=(PurchaseCostInput('international_shipping', '', 6000),)), expected_revision=purchase['revision'])
    source = tmp_path/'factura.pdf'; source.write_bytes(b'%PDF-1.4 test fixture')
    attached = AttachmentsRepository(cat.connection).add('purchase', purchase['id'], source)
    source.unlink()
    before = ProfitabilityRepository(cat.connection).report(date.today(), date.today())
    assert before['rows'][0]['cost_cents'] == 12000
    assert before['result_cents'] == 7500 and inv.rows()[0]['available'] == 2
    archive = tmp_path/'snapshot.zip'; preferences = {'sales/vat_enabled_default': False}
    create_backup(cat.connection, archive, preferences)
    sales.cancel(sale['id'])
    assert inv.rows()[0]['available'] == 3
    safety = prepare_restore(cat.connection, archive, preferences)
    assert safety.is_file()
    cat.close()
    apply_restore(db, lambda values: preferences.update(values))
    restored = CatalogRepository(db)
    try:
        assert ProfitabilityRepository(restored.connection).report(date.today(), date.today()) == before
        assert InventoryRepository(restored.connection).rows()[0]['available'] == 2
        attachments = AttachmentsRepository(restored.connection)
        assert attachments.path(attachments.list('purchase', purchase['id'])[0]).read_bytes() == b'%PDF-1.4 test fixture'
        assert restored.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not restored.connection.execute('PRAGMA foreign_key_check').fetchall()
    finally:
        restored.close()
