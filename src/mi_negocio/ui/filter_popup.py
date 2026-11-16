"""Panel emergente persistente: no desplaza la tabla al abrir filtros."""
from PySide6.QtCore import Qt,QPoint
from PySide6.QtWidgets import QFrame,QVBoxLayout,QPushButton
from .sales_widgets import note


class FilterPopup(QFrame):
    def __init__(self,title,parent=None):
        super().__init__(parent,Qt.Popup)
        self.setObjectName('saleSection')
        self.box=QVBoxLayout(self);self.box.setContentsMargins(16,12,16,12)
        self.box.addWidget(note(title,'cardTitle'))

    def finish(self):
        done=QPushButton('Listo');done.setObjectName('primary');done.clicked.connect(self.hide);self.box.addWidget(done)

    def open_below(self,button):
        self.adjustSize()
        screen=button.screen().availableGeometry();point=button.mapToGlobal(QPoint(0,button.height()+5))
        self.move(min(point.x(),screen.right()-self.width()),min(point.y(),screen.bottom()-self.height()))
        self.show()
