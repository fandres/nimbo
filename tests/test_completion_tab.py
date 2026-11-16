from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt
from mi_negocio.ui.purchase_line_editor import PurchaseLineDialog


@pytest.mark.parametrize('from_popup', [False, True])
@pytest.mark.parametrize('query,expected', [('fibra','2 · Láser fibra'),('laser','laser'),('zzz','zzz')])
def test_purchase_tab_accepts_only_unique_match(qtbot, query, expected, from_popup):
    products=[SimpleNamespace(id=1,code='1',name='Laser diodo'),SimpleNamespace(id=2,code='2',name='Láser fibra'),SimpleNamespace(id=3,code='3',name='Laser CO2')]
    dialog=PurchaseLineDialog(products);qtbot.addWidget(dialog);dialog.show();dialog.activateWindow();qtbot.waitActive(dialog)
    editor=dialog.product.lineEdit();editor.setFocus();qtbot.keyClicks(editor,query)
    qtbot.keyClick(dialog.product.completer().popup() if from_popup else editor,Qt.Key_Tab)
    assert dialog.product.currentText()==expected
    assert dialog.focusWidget() is dialog.quantity
    assert dialog.result_line is None


def test_expense_tab_restores_category(qtbot):
    from PySide6.QtWidgets import QWidget,QVBoxLayout,QLineEdit
    from mi_negocio.ui.expense_concept import ExpenseConceptEdit
    repo=SimpleNamespace(concept_suggestions=lambda text: [{'concept':'Facebook publicidad','category':'Marketing','category_id':7}] if len(text)>=3 else [])
    window=QWidget();layout=QVBoxLayout(window);edit=ExpenseConceptEdit(repo);next_field=QLineEdit();layout.addWidget(edit);layout.addWidget(next_field)
    qtbot.addWidget(window);window.show();window.activateWindow();qtbot.waitActive(window);edit.setFocus();selected=[];edit.concept_selected.connect(selected.append)
    qtbot.keyClicks(edit,'Fac');qtbot.keyClick(edit,Qt.Key_Tab)
    assert edit.text()=='Facebook publicidad'
    assert selected==[7]
    assert window.focusWidget() is next_field


def test_sale_tab_adds_unique_product_once_and_completes_city(qtbot,tmp_path):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.settings_repository import SettingsRepository
    from mi_negocio.sales_repository import SalesRepository
    from mi_negocio.ui.sale_dialog import SaleDialog
    cat=CatalogRepository(tmp_path/'db')
    product=cat.create(validate_product(ProductInput('001','Servicio laser','service','100')))
    dialog=SaleDialog(cat,SettingsRepository(cat.connection),SalesRepository(cat.connection));qtbot.addWidget(dialog);dialog.show()
    editor=dialog.product.lineEdit();editor.setFocus();qtbot.keyClicks(editor,'laser');qtbot.keyClick(editor,Qt.Key_Tab)
    qtbot.waitUntil(lambda:len(dialog.lines)==1)
    assert dialog.lines[0].product_id==product.id
    assert dialog.lines[0].quantity==1
    dialog.city.completer().model().setStringList(['Bogotá','Cali'])
    dialog.city.setText('Bog');qtbot.keyClick(dialog.city,Qt.Key_Tab)
    assert dialog.city.text()=='Bogotá'
    assert SalesRepository(cat.connection).list_sales()==[]
    dialog.close();cat.close()


def test_shift_tab_does_not_accept_suggestion(qtbot):
    dialog=PurchaseLineDialog([SimpleNamespace(id=1,code='1',name='Laser')]);qtbot.addWidget(dialog);dialog.show()
    editor=dialog.product.lineEdit();editor.setFocus();qtbot.keyClicks(editor,'Las')
    qtbot.keyClick(editor,Qt.Key_Backtab,Qt.ShiftModifier)
    assert dialog.product.currentText()=='Las'
