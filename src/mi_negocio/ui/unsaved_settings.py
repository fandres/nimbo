"""Track explicit-save configuration forms before a destructive restore."""
from PySide6.QtCore import QObject,Qt
from PySide6.QtWidgets import QLineEdit,QComboBox,QCheckBox,QSpinBox,QListWidget,QTableWidget,QPushButton


class UnsavedSettingsTracker(QObject):
    def __init__(self,editor):
        super().__init__(editor);self.editor=editor
        editor.setProperty('backupExplicitEditor',True)
        self.capture()
        editor.changed.connect(self.capture)
        for table in self.fields(QTableWidget):table.itemSelectionChanged.connect(self.capture)
        for listing in self.fields(QListWidget):
            if not any(listing.item(i).data(Qt.CheckStateRole) is not None for i in range(listing.count())):
                listing.currentRowChanged.connect(self.capture)
        for button in self.fields(QPushButton):
            if button.text() in ('Crear nueva','+ Nuevo concepto','+ Nueva categoría'):button.clicked.connect(self.capture)
        for name in ('scope','target'):
            combo=getattr(editor,name,None)
            if isinstance(combo,QComboBox):combo.currentIndexChanged.connect(self.capture)

    def fields(self,kind):
        result=[]
        for field in self.editor.findChildren(kind):
            parent=field.parentWidget()
            while parent is not None and parent!=self.editor and not parent.property('backupExplicitEditor'):parent=parent.parentWidget()
            if parent==self.editor:result.append(field)
        return result

    def values(self):
        result=[]
        for kind,read in ((QLineEdit,lambda w:w.text()),(QComboBox,lambda w:(w.currentIndex(),w.currentText())),
                          (QCheckBox,lambda w:w.isChecked()),(QSpinBox,lambda w:w.value()),
                          (QListWidget,lambda w:tuple((w.item(i).text(),w.item(i).checkState()) for i in range(w.count()) if w.item(i).data(Qt.CheckStateRole) is not None))):
            result.extend((id(w),read(w)) for w in self.fields(kind))
        return tuple(result)

    def capture(self,*_):self.baseline=self.values()
    def dirty(self):return self.values()!=self.baseline
