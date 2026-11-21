from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QLabel
from mi_negocio.repository import CatalogRepository
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.ui.home_page import HomePage
from mi_negocio.ui.style import HOME_ACTION_COLORS, STYLE


def test_full_cards_and_keyboard_trigger_correct_action_once(qtbot,tmp_path):
    repo=CatalogRepository(tmp_path/'db')
    page=HomePage(repo,sales=SalesRepository(repo.connection),purchases_available=True,expenses_available=True)
    qtbot.addWidget(page);page.setStyleSheet(STYLE);page.resize(1100,800);page.show()
    signals=[page.new_sale_requested,page.new_purchase_requested,page.new_expense_requested,page.pending_requested]
    for card,signal in zip(page.action_cards,signals):
        if card.layout():assert card.height() >= card.layout().minimumSize().height()
        assert card.cursor().shape()==Qt.PointingHandCursor
        assert all(label.testAttribute(Qt.WA_TransparentForMouseEvents) for label in card.findChildren(QLabel))
        with qtbot.waitSignal(signal):
            qtbot.mouseClick(card,Qt.LeftButton,pos=QPoint(card.width()-15,card.height()-15))
        card.setFocus()
        with qtbot.waitSignal(signal):
            qtbot.keyClick(card,Qt.Key_Space)
    assert HOME_ACTION_COLORS['purchases']=='#7040b0'
    repo.close()
