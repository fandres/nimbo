from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QStyle,QStyleOptionSpinBox
from mi_negocio.repository import CatalogRepository
from mi_negocio.purchases_repository import PurchasesRepository
from mi_negocio.ui.purchase_dialog import PurchaseDialog


def test_purchase_headers_fit_at_desktop_width(qtbot,tmp_path):
    c=CatalogRepository(tmp_path/'db')
    d=PurchaseDialog(c,PurchasesRepository(c.connection));qtbot.addWidget(d);d.resize(1180,740);d.show()
    for _ in range(4):QApplication.processEvents()
    table=d.lines_table;header=table.horizontalHeader();fm=header.fontMetrics()
    for column in range(table.columnCount()):
        text=table.horizontalHeaderItem(column).text()
        assert max(fm.horizontalAdvance(line) for line in text.splitlines())+20<=header.sectionSize(column)
        assert header.height()>=len(text.splitlines())*fm.height()
    d.close();c.close()


def test_spin_arrows_step_and_respect_limits(qtbot):
    from mi_negocio.ui.numeric_spinbox import NumericSpinBox
    spin=NumericSpinBox();qtbot.addWidget(spin)
    from mi_negocio.ui.style import STYLE
    spin.setStyleSheet(STYLE);spin.setRange(1,3);spin.setValue(2);spin.resize(150,42);spin.show()
    QApplication.processEvents()
    for control,expected in [(QStyle.SC_SpinBoxUp,3),(QStyle.SC_SpinBoxUp,3),(QStyle.SC_SpinBoxDown,2)]:
        option=QStyleOptionSpinBox();spin.initStyleOption(option)
        rect=spin.style().subControlRect(QStyle.CC_SpinBox,option,control,spin)
        assert rect.width()>=18 and rect.height()>=14
        qtbot.mouseClick(spin,Qt.LeftButton,pos=rect.center())
        assert spin.value()==expected
