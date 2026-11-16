from datetime import date
from PySide6.QtWidgets import QPushButton
from mi_negocio.repository import CatalogRepository
from mi_negocio.catalog import ProductInput,validate_product
from mi_negocio.purchases import PurchaseDraft,PurchaseLineInput
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.purchase_receipts_repository import PurchaseReceiptsRepository
from mi_negocio.ui.purchases_page import PurchasesPage


def test_inline_actions_and_shortcuts(qtbot,tmp_path,monkeypatch):
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    product=cat.create(validate_product(ProductInput('01','Máquina','product','100')))
    rows=[]
    for i in range(3):
        rows.append(repo.create(PurchaseDraft(date.today(),f'Proveedor {i}','',
            (PurchaseLineInput(product.id,1,10000),)),request_id=str(i)))
    PurchaseReceiptsRepository(cat.connection).receive(rows[0]['id'],date.today(),expected_revision=1)
    repo.cancel(rows[2]['id'],'Duplicado',expected_revision=1)
    page=PurchasesPage(cat,repo);qtbot.addWidget(page);page.resize(1440,900);page.show()
    assert page.month.currentData()==0
    assert page.year.currentData()==date.today().year
    assert len(page.rows)==2
    assert page.pending_count.text().startswith('2 ')
    assert page.receipt_count.text().startswith('1 ')
    assert set(page.row_receive_buttons)=={rows[1]['id']}
    page.row_receive_buttons[rows[1]['id']].click()
    assert page.dialog.purchase_id==rows[1]['id']
    page.dialog.reject()
    opened=[];monkeypatch.setattr(page,'_open',lambda purchase_id:opened.append(purchase_id))
    item=page.table.topLevelItem(0)
    page.table.itemWidget(item,6).findChildren(QPushButton)[0].click()
    assert opened==[rows[1]['id']]
    page.receipt_count.click()
    assert [row['id'] for row in page.rows]==[rows[1]['id']]
    page.pending_count.click()
    assert len(page.rows)==2
    page._clear_extra_filters()
    assert len(page.rows)==2
    page.close();cat.close()


def test_compact_popups_keep_table_position(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');page=PurchasesPage(cat,PurchasesRepository(cat.connection))
    qtbot.addWidget(page);page.resize(1440,900);page.show();qtbot.wait(20)
    before=page.table.geometry()
    page.date_button.click();qtbot.wait(20)
    assert page.date_popup.isVisible()
    page.use_dates.setChecked(True);qtbot.wait(20)
    assert all(widget.isEnabled() for widget in page.date_fields)
    assert page.table.geometry()==before
    page.date_popup.hide();page.more_button.click();qtbot.wait(20)
    assert page.more_popup.isVisible()
    assert page.table.geometry()==before
    page.close();cat.close()


def test_click_highlights_order_and_keeps_prices_readable(qtbot,tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette,QColor
    from PySide6.QtWidgets import QStyleOptionViewItem
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    product=cat.create(validate_product(ProductInput('01','Máquina','product','100')))
    for i in range(2):
        repo.create(PurchaseDraft(date.today(),f'Proveedor {i}','',
            (PurchaseLineInput(product.id,2,10000),)),request_id=str(i))
    page=PurchasesPage(cat,repo);qtbot.addWidget(page);page.resize(1440,900);page.show()
    # Reproduce a desktop theme with white selected text.
    palette=page.table.palette();palette.setColor(QPalette.HighlightedText,QColor('white'));page.table.setPalette(palette)
    qtbot.wait(20)
    first=page.table.topLevelItem(0);second=page.table.topLevelItem(1)
    qtbot.mouseClick(page.table.viewport(),Qt.LeftButton,pos=page.table.visualItemRect(first.child(0)).center())
    assert first.isSelected() and first.child(0).isSelected()
    assert not second.isSelected()
    assert first.text(5)
    option=QStyleOptionViewItem();page.table.itemDelegate().initStyleOption(option,page.table.indexFromItem(first,5))
    assert option.palette.color(QPalette.HighlightedText)==QColor('#162e50')
    # The heading is a widget; its underlying text must not be drawn twice on selection.
    page.table.itemDelegate().initStyleOption(option,page.table.indexFromItem(first,0))
    assert option.text==''
    qtbot.mouseClick(page.table.viewport(),Qt.LeftButton,pos=page.table.visualItemRect(second.child(0)).center())
    assert second.isSelected() and second.child(0).isSelected()
    assert not first.isSelected() and not first.child(0).isSelected()
    from PySide6.QtWidgets import QLabel
    heading=page.table.itemWidget(first,0).findChild(QLabel)
    qtbot.mouseClick(heading,Qt.LeftButton)
    assert first.isSelected() and first.child(0).isSelected()
    assert not second.isSelected()
    page.close();cat.close()
