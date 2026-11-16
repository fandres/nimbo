"""Comparación con QtPainter: sin dependencias ni redondeos en importes."""
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QColor
from PySide6.QtWidgets import QWidget,QSizePolicy
from .style import format_cop


class ComparisonChart(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.previous=0;self.current=0;self.captions=('Anterior','Actual')
        self.setMinimumHeight(170);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
    def set_values(self,previous,current,captions):
        self.previous=previous;self.current=current;self.captions=captions
        self.setAccessibleName(f'{captions[0]}: {format_cop(previous)}. {captions[1]}: {format_cop(current)}');self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        width=self.width();bottom=self.height()-42;top=36;available=max(1,bottom-top);maximum=max(self.previous,self.current,1)
        p.setPen(QColor('#e3e8f0'));p.drawLine(12,bottom,width-12,bottom)
        for i,(value,color) in enumerate([(self.previous,'#c8d3e9'),(self.current,'#315fda')]):
            center=width*(.27 if i==0 else .73);bar_width=min(100,width*.27);height=available*(value/maximum)
            p.setPen(Qt.NoPen);p.setBrush(QColor(color));p.drawRoundedRect(QRectF(center-bar_width/2,bottom-height,bar_width,max(1,height)),7,7)
            p.setPen(QColor('#183052'));p.drawText(QRectF(center-width*.23,max(0,bottom-height-30),width*.46,26),Qt.AlignCenter,format_cop(value))
            p.setPen(QColor('#64748b'));p.drawText(QRectF(center-width*.23,bottom+6,width*.46,34),Qt.AlignCenter|Qt.TextWordWrap,self.captions[i])
