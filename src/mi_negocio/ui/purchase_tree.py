"""Árbol de compras con nombres completos y altura adaptable."""
from PySide6.QtCore import Qt, QRect, QSignalBlocker, QTimer
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QTreeWidget, QStyledItemDelegate, QStyleOptionViewItem


class WrappedPurchaseDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option,index)
        # Native Linux themes may use white selected text. Keep prices legible.
        option.palette.setColor(QPalette.Highlight,QColor('#e5edff'))
        option.palette.setColor(QPalette.HighlightedText,QColor('#162e50'))
        tree=self.parent()
        if tree.itemWidget(tree.itemFromIndex(index),index.column()) is not None:
            option.text=''

    def sizeHint(self, option, index):
        result=super().sizeHint(option,index)
        if index.column()==0:
            tree=self.parent()
            depth=2 if index.parent().isValid() else 1
            width=max(80,tree.columnWidth(0)-tree.indentation()*depth-24)
            widget=tree.itemWidget(tree.itemFromIndex(index),0)
            if widget is not None:
                # Embedded labels wrap using their own fonts, spacing and margins.
                # The plain item text cannot predict the height of this layout.
                layout=widget.layout()
                margins=layout.contentsMargins()
                label_width=max(1,width-margins.left()-margins.right())
                # QVBoxLayout can shrink wrapped labels to their one-line hint.
                # Reserve each label's actual wrapped height on native Windows too.
                for position in range(layout.count()):
                    label=layout.itemAt(position).widget()
                    if label is not None and label.hasHeightForWidth():
                        label.setMinimumHeight(label.heightForWidth(label_width))
                required=layout.totalHeightForWidth(width)
                result.setHeight(max(result.height(),required+26))
                return result
            bounds=option.fontMetrics.boundingRect(QRect(0,0,width,10000),Qt.TextWordWrap,index.data() or '')
            result.setHeight(max(result.height(),bounds.height()+26))
        return result

    def paint(self,painter,option,index):
        opt=QStyleOptionViewItem(option)
        opt.textElideMode=Qt.ElideNone
        opt.features |= QStyleOptionViewItem.WrapText
        super().paint(painter,opt,index)


class PurchaseTree(QTreeWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setItemDelegate(WrappedPurchaseDelegate(self))
        self.setWordWrap(True)
        self.setSelectionBehavior(QTreeWidget.SelectRows)
        self._relayout=QTimer(self)
        self._relayout.setSingleShot(True)
        self._relayout.timeout.connect(self.doItemsLayout)
        self.header().sectionResized.connect(lambda *_:self._relayout.start(0))
        self.itemSelectionChanged.connect(self._select_order)

    def _select_order(self):
        selected=self.selectedItems()
        if not selected:return
        parent=selected[0]
        while parent.parent() is not None:parent=parent.parent()
        with QSignalBlocker(self):
            self.clearSelection()
            parent.setSelected(True)
            for i in range(parent.childCount()):parent.child(i).setSelected(True)
        self.viewport().update()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.doItemsLayout()
