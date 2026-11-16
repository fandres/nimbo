"""Signed net cash plot; zero is always visible."""
from datetime import date,timedelta
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget
from .style import format_cop

class MoneyChart(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.points=[];self.setMinimumHeight(210);self.setMinimumWidth(280)
    def set_rows(self,rows,start,end,monthly=False):
        totals={};day=start
        while day<=end:
            key=day.strftime('%Y-%m') if monthly else (start+timedelta(days=((day-start).days//7)*7)).isoformat()
            totals.setdefault(key,0);day+=timedelta(days=1)
        for row in rows:
            day=date.fromisoformat(row['date']);key=day.strftime('%Y-%m') if monthly else (start+timedelta(days=((day-start).days//7)*7)).isoformat()
            if key in totals:totals[key]+=row['delta']
        self.points=list(totals.items());self.setToolTip('\n'.join(f'{k}: {format_cop(v)}' for k,v in self.points));self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height();left,right,top,bottom=78,w-20,25,h-35
        values=[v for _,v in self.points];lo=min([0]+values);hi=max([0]+values)
        if hi==lo:hi=100
        def y(v):return bottom-(v-lo)/(hi-lo)*(bottom-top)
        p.setPen(QColor('#dce3ef'))
        for value in (lo,0,hi):
            p.drawLine(QPointF(left,y(value)),QPointF(right,y(value)))
            p.setPen(QColor('#64748b'));p.drawText(0,int(y(value))-8,left-7,18,Qt.AlignRight, f'{value/100000000:.1f} M');p.setPen(QColor('#dce3ef'))
        coords=[QPointF(left+i*(right-left)/max(1,len(values)-1),y(value)) for i,value in enumerate(values)]
        for i in range(1,len(coords)):
            a,b=coords[i-1],coords[i];va,vb=values[i-1],values[i]
            if va*vb<0:
                t=abs(va)/(abs(va)+abs(vb));middle=QPointF(a.x()+t*(b.x()-a.x()),y(0))
                p.setPen(QPen(QColor('#168454' if va>0 else '#c63745'),2));p.drawLine(a,middle)
                p.setPen(QPen(QColor('#168454' if vb>0 else '#c63745'),2));p.drawLine(middle,b)
            else:p.setPen(QPen(QColor('#168454' if max(va,vb)>0 else '#c63745' if min(va,vb)<0 else '#64748b'),2));p.drawLine(a,b)
        stride=max(1,len(coords)//6)
        for i,point in enumerate(coords):
            color=QColor('#168454' if values[i]>0 else '#c63745' if values[i]<0 else '#64748b')
            p.setBrush(color);p.setPen(color);p.drawEllipse(point,4,4)
            if i%stride==0:
                p.setPen(QColor('#64748b'));p.drawText(int(point.x())-35,h-25,70,20,Qt.AlignCenter,self.points[i][0][5:])
