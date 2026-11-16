"""Período compartido entre Resumen y Movimientos, sin desplazar contenidos."""
from datetime import date
from calendar import monthrange
from PySide6.QtCore import Signal,QDate
from PySide6.QtWidgets import QPushButton,QComboBox,QHBoxLayout,QCheckBox
from .filter_popup import FilterPopup
from .sales_widgets import date_edit,note
from ..storage import StorageError

MONTHS=('Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre')


class ExpensePeriod(QPushButton):
    changed=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.popup=FilterPopup('Período de gastos',self)
        row=QHBoxLayout();self.month=QComboBox();self.year=QComboBox();today=date.today()
        for i,name in enumerate(MONTHS,1):self.month.addItem(name,i)
        self.month.setCurrentIndex(today.month-1);self.selected_year=today.year
        for year in range(today.year,today.year-6,-1):self.year.addItem(str(year),year)
        self.year.addItem('Más años anteriores…',None);row.addWidget(self.month);row.addWidget(self.year);self.popup.box.addLayout(row)
        self.custom=QCheckBox('Rango personalizado');self.popup.box.addWidget(self.custom)
        row=QHBoxLayout();self.start=date_edit();self.end=date_edit();self.start.setDate(QDate(today.year,today.month,1))
        for title,w in [('Desde',self.start),('Hasta',self.end)]:row.addWidget(note(title));row.addWidget(w)
        self.popup.box.addLayout(row);self.popup.finish();self.clicked.connect(lambda:self.popup.open_below(self))
        self.month.currentIndexChanged.connect(self._month);self.year.currentIndexChanged.connect(self._year)
        self.custom.toggled.connect(self._update);self.start.dateChanged.connect(self._update);self.end.dateChanged.connect(self._update);self._update()
    def _month(self):self.custom.setChecked(False);self._update()
    def _year(self):
        value=self.year.currentData()
        if value is None:
            oldest=self.year.itemData(self.year.count()-2);self.year.blockSignals(True);self.year.removeItem(self.year.count()-1)
            for year in range(oldest-1,max(0,oldest-6),-1):self.year.addItem(str(year),year)
            if oldest>6:self.year.addItem('Más años anteriores…',None)
            self.year.setCurrentIndex(self.year.findData(self.selected_year));self.year.blockSignals(False);self.year.showPopup();return
        self.selected_year=value;self._month()
    def period(self):
        if self.custom.isChecked():
            start,end=self.start.date().toPython(),self.end.date().toPython()
            if start>end:raise StorageError('La fecha inicial debe ser anterior o igual a la final.')
            return start,end,False
        year,month=self.year.currentData(),self.month.currentData();today=date.today()
        start=date(year,month,1);end=date(year,month,monthrange(year,month)[1])
        if start>today:raise StorageError('Selecciona un período que ya haya comenzado.')
        return start,min(end,today),True
    def _update(self,*args):
        self.start.setEnabled(self.custom.isChecked());self.end.setEnabled(self.custom.isChecked())
        try:
            start,end,_=self.period();self.setText(f'{start:%d/%m/%Y} – {end:%d/%m/%Y}')
        except StorageError:self.setText('Revisar período')
        self.changed.emit()
