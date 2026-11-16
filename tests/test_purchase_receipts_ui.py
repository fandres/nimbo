from datetime import date
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.purchase_receipts_repository import PurchaseReceiptsRepository
from mi_negocio.ui.purchase_receipt_dialog import PurchaseReceiptDialog
from mi_negocio.ui.purchases_page import PurchasesPage
from mi_negocio.ui.purchase_dialog import PurchaseDialog


def test_receipt_warning_and_selection(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection);receipts=PurchaseReceiptsRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    row=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,3,100),)),request_id='1')
    page=PurchasesPage(cat,repo);qtbot.addWidget(page);page.show()
    page.table.setCurrentItem(page.table.topLevelItem(0).child(0));page.open_receipt()
    dlg=page.dialog;qtbot.addWidget(dlg)
    assert dlg.warning.isVisible() and dlg.confirm.isEnabled()
    assert dlg.received_on.date().toPython()==date.today()
    dlg.save();assert receipts.current(row['id']) is not None
    assert row['id'] not in page.row_receive_buttons
    page.received_filter.setCurrentIndex(1);assert not page.rows
    page.received_filter.setCurrentIndex(2);assert len(page.rows)==1
    edit=PurchaseDialog(cat,repo,purchase_id=row['id']);qtbot.addWidget(edit);edit.show()
    assert edit.reverse_receipt_button.isVisible() and not edit.add_line.isEnabled()
    line=edit.open_line_editor(0);qtbot.addWidget(line);assert not line.quantity.isEnabled()
    line.close();edit.close();page.close();cat.close()


def test_receipt_stale_preserves_dialog(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection);receipts=PurchaseReceiptsRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    draft=PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,100),))
    row=repo.create(draft,request_id='1');dlg=PurchaseReceiptDialog(repo,receipts,row['id']);qtbot.addWidget(dlg);dlg.show()
    repo.update(row['id'],draft,expected_revision=1)
    dlg.save();assert dlg.isVisible() and dlg.error.text()
    assert receipts.current(row['id']) is None
    dlg.reject();cat.close()


def test_history_receipt_read_error_is_shown(qtbot,tmp_path,monkeypatch):
    from mi_negocio.storage import StorageError
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    row=repo.create(PurchaseDraft(date.today(),'Proveedor','',(PurchaseLineInput(p.id,1,100),)),request_id='1')
    dlg=PurchaseDialog(cat,repo,purchase_id=row['id']);qtbot.addWidget(dlg)
    def fail(*args):raise StorageError('Base ocupada')
    monkeypatch.setattr(PurchaseReceiptsRepository,'history',fail)
    dlg.show_history()
    assert dlg.error.text()=='Base ocupada'
    cat.close()
