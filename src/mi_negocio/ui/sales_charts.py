"""Sales charts drawn with Qt, with exact amounts available on hover."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QSizePolicy, QToolTip
from .style import format_cop


class SalesEvolutionChart(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.current=[];self.previous=[];self.regions=[]
        self.setMinimumHeight(165);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);self.setMouseTracking(True)

    def set_values(self,current,previous):
        self.current=current;self.previous=previous
        self.setAccessibleName('Evolución de ventas. '+'. '.join(b['label']+': '+format_cop(b['value']) for b in current));self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);self.regions=[]
        if not self.current:
            p.setPen(QColor('#657895'));p.drawText(self.rect(),Qt.AlignCenter,'Sin ventas en este período');return
        n=max(len(self.current),len(self.previous));width=self.width();bottom=self.height()-42;top=24
        maximum=max([b['value'] for b in self.current+self.previous]+[1]);left=48;slot=max(1,(width-left-8)/n)
        p.setPen(QColor('#e4e9f2'))
        for i in range(4):
            y=bottom-(bottom-top)*i/3;p.drawLine(left,int(y),width-5,int(y))
            p.setPen(QColor('#657895'));p.drawText(QRectF(0,y-10,left-6,20),Qt.AlignRight|Qt.AlignVCenter,f'{maximum*i/3/100000000:.1f}');p.setPen(QColor('#e4e9f2'))
        p.setPen(QColor('#657895'));p.drawText(QRectF(0,0,100,20),Qt.AlignLeft,'Millones COP')
        for index in range(n):
            center=left+slot*(index+.5);bar=min(34,slot*.30)
            for sequence,shift,color,title in [(self.current,-bar*.55,'#315bea','Actual'),(self.previous,bar*.55,'#c7d2e8','Anterior')]:
                if index>=len(sequence):continue
                item=sequence[index]
                if item.get('empty'):continue
                height=(bottom-top)*item['value']/maximum
                rect=QRectF(center+shift-bar/2,bottom-height,bar,height)
                p.setPen(Qt.NoPen);p.setBrush(QColor(color));p.drawRoundedRect(rect,4,4)
                hit=QRectF(center+shift-bar/2,top,bar,bottom-top)
                self.regions.append((hit,f"{title}: {item['start']:%d/%m/%Y} – {item['end']:%d/%m/%Y}\n{format_cop(item['value'])}"))
            label=self.current[index]['label'] if index<len(self.current) else 'Anterior'
            p.setPen(QColor('#657895'));p.drawText(QRectF(center-slot/2,bottom+5,slot,36),Qt.AlignCenter|Qt.TextWordWrap,label)
        p.end()

    def mouseMoveEvent(self,event):
        for rect,text in self.regions:
            if rect.contains(event.position()):QToolTip.showText(event.globalPosition().toPoint(),text,self);return
        QToolTip.hideText()


class CollectionBar(QWidget):
    def __init__(self):
        super().__init__();self.received=0;self.pending=0;self.setFixedHeight(18)
    def set_values(self,received,pending):
        self.received=received;self.pending=pending;self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen)
        p.setBrush(QColor('#edf1f8'));p.drawRoundedRect(self.rect(),5,5)
        total=self.received+self.pending
        if total:
            p.setBrush(QColor('#315bea'));p.drawRect(QRectF(0,0,self.width()*self.received/total,self.height()))
            p.setBrush(QColor('#efb649'));p.drawRect(QRectF(self.width()*self.received/total,0,self.width()*self.pending/total,self.height()))
