"""Gráfica mensual accesible y navegable desde Inicio."""
from decimal import Decimal
from PySide6.QtCore import Qt,QRectF,Signal
from PySide6.QtGui import QPainter,QColor
from PySide6.QtWidgets import QWidget,QToolTip,QSizePolicy
from .style import format_cop
from .expense_filters import MONTHS


def compact_money(cents):
    if abs(cents)>=100000000:return '$ '+str((Decimal(cents)/100000000).quantize(Decimal('.1'))).replace('.',',')+' M'
    if abs(cents)>=100000:return '$ '+str((Decimal(cents)/100000).quantize(Decimal('.1'))).replace('.',',')+' mil'
    return format_cop(cents)


class HomeChart(QWidget):
    period_requested=Signal(object,object)
    def __init__(self,parent=None):
        super().__init__(parent);self.rows=[];self.regions=[];self.selected=5
        self.setMinimumHeight(210);self.setMinimumWidth(0);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.setMouseTracking(True);self.setFocusPolicy(Qt.StrongFocus);self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('Haz clic en un mes para ver sus ventas. Teclado: flechas y Enter.')
    def set_values(self,rows):
        self.rows=rows;self.regions=[]
        self.setAccessibleName('Ventas por mes. '+'. '.join(f"{r['start']:%m/%Y}: {format_cop(r['value'])}" for r in rows));self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);self.regions=[]
        if not self.rows:
            p.setPen(QColor('#657895'));p.drawText(self.rect(),Qt.AlignCenter,'Sin datos disponibles');return
        left=68;top=28;bottom=self.height()-45;plot=max(1,self.width()-left-8);slot=plot/len(self.rows)
        maximum=max([r['value'] for r in self.rows]+[100]);scale=Decimal(maximum)
        for step in range(4):
            y=bottom-(bottom-top)*step/3
            p.setPen(QColor('#e6eaf3'));p.drawLine(left,int(y),self.width()-4,int(y))
            p.setPen(QColor('#657895'));p.drawText(QRectF(0,y-10,left-8,20),Qt.AlignRight|Qt.AlignVCenter,compact_money(maximum*step//3))
        for i,row in enumerate(self.rows):
            x=left+slot*i;bar=min(58,slot*.58);height=float(Decimal(row['value'])/scale)*(bottom-top)
            rect=QRectF(x+(slot-bar)/2,bottom-max(2,height),bar,max(2,height))
            p.setPen(Qt.NoPen);p.setBrush(QColor('#315bea' if i==len(self.rows)-1 else '#cbd3e8'));p.drawRoundedRect(rect,6,6)
            p.setPen(QColor('#183052'));p.drawText(QRectF(x,rect.top()-23,slot,20),Qt.AlignCenter,compact_money(row['value']))
            p.setPen(QColor('#657895'));month=MONTHS[row['start'].month-1][:3].lower()
            p.drawText(QRectF(x,bottom+4,slot,38),Qt.AlignCenter,month+('\nen curso' if i==len(self.rows)-1 else ''))
            hit=QRectF(x,top,slot,self.height()-top);self.regions.append((hit,row))
            if self.hasFocus() and i==self.selected:
                p.setPen(QColor('#315bea'));p.setBrush(Qt.NoBrush);p.drawRoundedRect(hit.adjusted(2,0,-2,-1),4,4)
        p.end()
    def mouseMoveEvent(self,event):
        for rect,row in self.regions:
            if rect.contains(event.position()):
                QToolTip.showText(event.globalPosition().toPoint(),f"{row['start']:%d/%m/%Y} – {row['end']:%d/%m/%Y}\n{format_cop(row['value'])}\nClic para ver las ventas",self);return
        QToolTip.hideText()
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:
            for rect,row in self.regions:
                if rect.contains(event.position()):self.period_requested.emit(row['start'],row['end']);return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Left,Qt.Key_Right):
            self.selected=max(0,min(len(self.rows)-1,self.selected+(-1 if event.key()==Qt.Key_Left else 1)));self.update();return
        if event.key() in (Qt.Key_Return,Qt.Key_Enter,Qt.Key_Space) and self.rows:
            row=self.rows[self.selected];self.period_requested.emit(row['start'],row['end']);return
        super().keyPressEvent(event)
    def focusInEvent(self,event):super().focusInEvent(event);self.update()
    def focusOutEvent(self,event):super().focusOutEvent(event);self.update()
