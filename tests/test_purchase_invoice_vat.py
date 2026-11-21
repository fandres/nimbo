from dataclasses import replace
from datetime import date
from decimal import Decimal
import pytest
from mi_negocio.catalog import ProductInput, ValidationError, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import (PurchaseDraft, PurchaseLineInput, PurchaseCostInput,
    calculate_purchase_totals, line_vat_cop, line_base_cop, apply_invoice_vat)
from mi_negocio.purchases_repository import PurchasesRepository, draft_from_record


def draft(lines=None, **kwargs):
    return PurchaseDraft(date.today(), 'Proveedor', '', tuple(lines or [PurchaseLineInput(1, 1, 119000)]),
                         invoice_vat_enabled=True, **kwargs)


def test_total_vat_rounds_once_and_preserves_original_amounts():
    d=draft([PurchaseLineInput(1,1,1),PurchaseLineInput(2,1,3)])
    n=apply_invoice_vat(d)
    assert sum(line_vat_cop(l) for l in n.lines)==1
    assert sum(line_base_cop(l) for l in n.lines)==3
    assert [l.unit_cost_cents for l in n.lines]==[1,3]
    assert apply_invoice_vat(n)==n
    restored=apply_invoice_vat(replace(n,invoice_vat_enabled=False))
    assert sum(line_base_cop(l) for l in restored.lines)==4
    assert sum(line_vat_cop(l) for l in restored.lines)==0


def test_global_vat_mixed_currencies_and_rate():
    d=draft([PurchaseLineInput(1,1,100,'USD',Decimal('4100'),date.today()),PurchaseLineInput(2,2,33000)])
    totals=calculate_purchase_totals(d)
    assert (totals.merchandise_cents,totals.vat_cents,totals.total_cents)==(400000,76000,476000)
    assert calculate_purchase_totals(draft(invoice_vat_rate=Decimal('5'))).vat_cents==5667


@pytest.mark.parametrize('case',['line','manual','invalid_rate'])
def test_global_vat_rejects_conflicting_modes(case):
    d=draft()
    if case=='line':d=replace(d,lines=(replace(d.lines[0],vat_enabled=True),))
    elif case=='manual':d=replace(d,costs=(PurchaseCostInput('taxes','IVA factura',100),))
    else:d=replace(d,invoice_vat_rate=Decimal('NaN'))
    with pytest.raises(ValidationError):calculate_purchase_totals(d)


def test_repository_roundtrip_history_and_disable(tmp_path):
    cat=CatalogRepository(tmp_path/'db')
    p=cat.create(validate_product(ProductInput('P','Máquina','product','100')))
    repo=PurchasesRepository(cat.connection)
    row=repo.create(draft([PurchaseLineInput(p.id,1,119000)]),request_id='global')
    assert row['invoice_vat_enabled']==1
    assert row['lines'][0]['subtotal_cents']==100000
    assert row['lines'][0]['vat_cents']==19000
    assert row['total_cents']==119000
    d=draft_from_record(row)
    assert calculate_purchase_totals(d).vat_cents==19000
    updated=repo.update(row['id'],replace(d,invoice_vat_enabled=False),expected_revision=row['revision'])
    assert updated['lines'][0]['subtotal_cents']==119000
    assert updated['lines'][0]['vat_cents']==0
    assert updated['revisions'][0]['snapshot']['totals']['vat_cents']==19000
    assert cat.connection.execute('PRAGMA user_version').fetchone()[0]==29
    cat.close()


def test_dialog_global_toggle_live_totals_reopen_and_conflict(qtbot,tmp_path):
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db')
    p=cat.create(validate_product(ProductInput('P','Máquina','product','100')))
    repo=PurchasesRepository(cat.connection)
    d=PurchaseDialog(cat,repo);qtbot.addWidget(d)
    d.supplier.setText('Proveedor');d.lines=[PurchaseLineInput(p.id,1,119000)];d.refresh_lines()
    d.invoice_vat_enabled.setChecked(True)
    assert '190,00' in d.invoice_vat_summary.text()
    assert '1.000,00' in d.products_total.text()
    child=d.open_line_editor(0);qtbot.addWidget(child)
    assert not child.vat.enabled.isEnabled()
    child.reject()
    d.save()
    saved=repo.list_purchases()[0]
    reopened=PurchaseDialog(cat,repo,purchase_id=saved['id']);qtbot.addWidget(reopened)
    assert reopened.invoice_vat_enabled.isChecked()
    assert reopened.lines[0].invoice_vat_share_cents==19000
    reopened.invoice_vat_enabled.setChecked(False)
    assert '1.190,00' in reopened.products_total.text()
    reopened.lines=[replace(reopened.lines[0],vat_enabled=True)]
    reopened.refresh_lines();reopened.invoice_vat_enabled.setChecked(True)
    assert not reopened.invoice_vat_enabled.isChecked()
    assert 'IVA' in reopened.error.text()
    cat.close()


def test_global_vat_geometry_and_invalid_rate(qtbot,tmp_path):
    from PySide6.QtWidgets import QApplication
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('P','Máquina','product','100')))
    d=PurchaseDialog(cat,repo);qtbot.addWidget(d)
    d.lines=[PurchaseLineInput(p.id,1,119000)];d.refresh_lines()
    d.invoice_vat_enabled.setChecked(True);d.resize(1280,720);d.show()
    for _ in range(3):QApplication.processEvents()
    assert d.scroll.verticalScrollBar().maximum()==0
    assert d.scroll.horizontalScrollBar().maximum()==0
    d.invoice_vat_rate.clear()
    assert 'Revisa' in d.summary_labels[-1].text()
    d.invoice_vat_enabled.setChecked(False)
    assert '1.190,00' in d.summary_labels[-1].text()
    cat.close()


def test_invoice_vat_migration_preserves_old_amounts_and_backup(tmp_path):
    from mi_negocio.database import open_database
    path=tmp_path/'db';cat=CatalogRepository(path)
    p=cat.create(validate_product(ProductInput('P','Máquina','product','100')))
    repo=PurchasesRepository(cat.connection)
    row=repo.create(replace(draft([PurchaseLineInput(p.id,1,119000)]),invoice_vat_enabled=False),request_id='old')
    for column in ('invoice_vat_enabled','invoice_vat_rate'):
        cat.connection.execute('ALTER TABLE purchases DROP COLUMN '+column)
    cat.connection.execute('PRAGMA user_version=25');cat.connection.commit();cat.close()
    connection=open_database(path)
    migrated=PurchasesRepository(connection).get(row['id'])
    assert migrated['invoice_vat_enabled']==0
    assert migrated['lines'][0]['subtotal_cents']==119000
    assert migrated['lines'][0]['vat_cents']==0
    assert list(tmp_path.glob('db.backup-*'))
    connection.close()
