from datetime import date
from PySide6.QtCore import Qt
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.ui.purchases_page import PurchasesPage


def test_children_and_pending_filter(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db'); repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    d=PurchaseDraft(date.today(),'Proveedor','REF',(PurchaseLineInput(p.id,2,10000),PurchaseLineInput(p.id,1,20000)),
        cost_states=dict(international_shipping='pending',importation='pending',taxes='pending',other='not_applicable'))
    row=repo.create(d,request_id='1'); page=PurchasesPage(cat,repo); qtbot.addWidget(page)
    parent=page.table.topLevelItem(0)
    assert parent.childCount()==2 and parent.isExpanded()
    assert '001' in parent.child(0).text(0)
    assert parent.child(0).data(0,Qt.UserRole)==row['id']
    page.search.setText('001'); assert page.table.topLevelItemCount()==1
    page.progress_filter.setCurrentIndex(page.progress_filter.findData('nationalization_pending'))
    assert page.table.topLevelItemCount()==1
    assert '1 pedidos' in page.pending_count.text()
    page.table.setCurrentItem(page.table.topLevelItem(0).child(1)); page.open_detail()
    assert page.dialog.purchase_id==row['id']; page.dialog.close(); cat.close()


def test_pending_costs_heading_fits_wrapped_labels(qtbot,tmp_path):
    from PySide6.QtWidgets import QLabel,QHeaderView
    from PySide6.QtGui import QFont
    from mi_negocio.purchases import CATEGORIES
    cat=CatalogRepository(tmp_path/'db');repo=PurchasesRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('001','Máquina','product','1')))
    repo.create(PurchaseDraft(date.today(),'Shandong Elegant Industrial Technology','',
        (PurchaseLineInput(p.id,1,10000),),cost_states={key:'pending' for key in CATEGORIES}),request_id='pending')
    page=PurchasesPage(cat,repo);qtbot.addWidget(page)
    from mi_negocio.ui.style import STYLE
    page.setStyleSheet(STYLE)
    page.setFont(QFont('Sans Serif',12));page.resize(1440,900);page.show()
    page.table.header().setSectionResizeMode(0,QHeaderView.Interactive)
    for width in (300,220,400):
        page.table.setColumnWidth(0,width);qtbot.wait(30)
        item=page.table.topLevelItem(0);widget=page.table.itemWidget(item,0)
        for label in widget.findChildren(QLabel):
            assert label.height() >= label.heightForWidth(label.width()), (label.text(),label.size())
            assert label.geometry().bottom() < widget.height()
    cat.close()
