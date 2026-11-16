"""Compact sales overview, sharing the list's active filters."""
from datetime import date
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFrame,
    QComboBox,QScrollArea,QProgressBar,QSizePolicy,QPushButton)
from ..sales_analytics import evolution,comparative_evolution
from .sales_widgets import note
from .sales_charts import SalesEvolutionChart,CollectionBar
from .style import format_cop


def card(title,action=False):
    frame=QPushButton() if action else QFrame();
    if action:
        frame.setAutoDefault(False);frame.setCursor(Qt.PointingHandCursor)
        frame.setStyleSheet('QPushButton { background: white; border: 1px solid #e3e8f0; border-radius: 12px; padding: 0; } QPushButton:hover { background: #f0f4ff; border-color: #a8b9ee; } QPushButton:focus { border: 2px solid #315bea; }')
    frame.setObjectName('saleSection')
    box=QVBoxLayout(frame);box.setContentsMargins(14,10,14,10);box.setSpacing(6)
    if title:
        label=note(title,'cardTitle');label.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed);box.addWidget(label)
    return frame,box


class SalesDashboard(QScrollArea):
    movements_requested=Signal(bool)
    def __init__(self,parent=None):
        super().__init__(parent);self.data=None;self.rows=[];self.previous=[];self.dates=None
        self.setWidgetResizable(True);self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body=QWidget();self.body.setObjectName('salesDashboardBody');self.body.setStyleSheet('QWidget#salesDashboardBody { background: #f4f6fc; } QComboBox { padding: 4px 8px; min-height: 20px; }');self.setWidget(self.body);root=QVBoxLayout(self.body);root.setContentsMargins(0,0,0,0);root.setSpacing(12)
        self.kpis=QGridLayout();self.kpi_cards=[];self.values={};self.hints={}
        for key,title in [('total','VENTAS DEL PERÍODO'),('count','VENTAS REALIZADAS'),('average','VALOR PROMEDIO'),('pending','POR COBRAR')]:
            actionable=key in ('total','count','pending')
            frame,box=card('',actionable);caption=note(title);caption.setStyleSheet('font-size: 11px; color: #657895;');box.addWidget(caption)
            value=note('—');value.setStyleSheet('font-size: 23px; font-weight: 700; color: '+('#975d00' if key=='pending' else '#162e50')+';');box.addWidget(value)
            hint=note('');hint.setStyleSheet('font-size: 11px; color: #657895;');box.addWidget(hint)
            if actionable:
                frame.setAccessibleName('Ver ventas pendientes de cobro' if key=='pending' else 'Ver ventas del período')
                frame.setToolTip(frame.accessibleName())
                for label in (caption,value,hint):label.setAttribute(Qt.WA_TransparentForMouseEvents)
                frame.clicked.connect(lambda checked=False,k=key:self.movements_requested.emit(k=='pending'))
            self.values[key]=value;self.hints[key]=hint;self.kpi_cards.append(frame)
        root.addLayout(self.kpis)
        self.middle=QGridLayout();self.middle.setSpacing(12)
        self.trend_frame,trend=card('Evolución de ventas')
        controls=QHBoxLayout();self.scale=QComboBox();self.scale.addItem('Por mes','month');self.scale.addItem('Por semana','week');controls.addWidget(self.scale);controls.addStretch();trend.addLayout(controls)
        self.chart=SalesEvolutionChart();trend.addWidget(self.chart,1)
        self.legend=note('● Actual     ○ Anterior · Pasa el cursor para ver fechas e importes');self.legend.setStyleSheet('font-size: 11px; color: #657895;');trend.addWidget(self.legend)
        self.rank_frame,ranking=card('Más vendidos')
        selectors=QHBoxLayout();self.kind=QComboBox();self.kind.addItem('Productos / máquinas','products');self.kind.addItem('Servicios','services');self.rank_metric=QComboBox();self.rank_metric.addItem('Unidades','units');self.rank_metric.addItem('Valor vendido','value');selectors.addWidget(self.kind,1);selectors.addWidget(self.rank_metric);ranking.addLayout(selectors)
        self.rank_grid=QGridLayout();self.rank_grid.setVerticalSpacing(6);self.rank_grid.setColumnStretch(0,2);self.rank_grid.setColumnStretch(1,3);self.rank_rows=[]
        for i in range(5):
            label=note('');label.setMinimumWidth(0);label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
            bar=QProgressBar();bar.setRange(0,1000);bar.setTextVisible(False);bar.setFixedHeight(12);bar.setStyleSheet('QProgressBar { border: 0; border-radius: 6px; background: #eef2fa; } QProgressBar::chunk { background: #315bea; border-radius: 6px; }')
            value=note('');value.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.rank_grid.addWidget(label,i,0);self.rank_grid.addWidget(bar,i,1);self.rank_grid.addWidget(value,i,2);self.rank_rows.append((label,bar,value))
        ranking.addLayout(self.rank_grid,1);self.rank_hint=note('');self.rank_hint.setStyleSheet('font-size: 11px; color: #657895;');ranking.addWidget(self.rank_hint)
        root.addLayout(self.middle,1)
        self.bottom=QGridLayout();self.bottom.setSpacing(12)
        self.collection_frame,collection=card('Cobros de estas ventas');self.collection_bar=CollectionBar();collection.addWidget(self.collection_bar)
        self.collection_text=note('');collection.addWidget(self.collection_text)
        hint=note('Importes brutos de estas ventas, no flujo de caja por fecha de cobro.');hint.setStyleSheet('font-size: 11px; color: #657895;');collection.addWidget(hint)
        self.cost_frame,costs=card('Comisiones y envíos');self.cost_values={}
        for key,title in [('commissions','Comisiones'),('shipping_cost','Costo de envíos'),('shipping_charged','Envío cobrado al cliente')]:
            row=QHBoxLayout();row.addWidget(note(title),1);value=note('—');row.addWidget(value);costs.addLayout(row);self.cost_values[key]=value
        self.cost_hint=note('');self.cost_hint.setStyleSheet('font-size: 11px; color: #657895;');costs.addWidget(self.cost_hint)
        root.addLayout(self.bottom)
        self.scale.currentIndexChanged.connect(self.refresh_chart);self.kind.currentIndexChanged.connect(self.refresh_ranking);self.rank_metric.currentIndexChanged.connect(self.refresh_ranking)
        self._compact=None;self.arrange(False)

    def arrange(self,compact):
        if self._compact==compact:return
        self._compact=compact
        for layout in (self.kpis,self.middle,self.bottom):
            while layout.count():layout.takeAt(0)
        for i,frame in enumerate(self.kpi_cards):self.kpis.addWidget(frame,i//2 if compact else 0,i%2 if compact else i)
        self.middle.addWidget(self.trend_frame,0,0);self.middle.addWidget(self.rank_frame,1 if compact else 0,0 if compact else 1)
        self.bottom.addWidget(self.collection_frame,0,0);self.bottom.addWidget(self.cost_frame,1 if compact else 0,0 if compact else 1)
        self.middle.setColumnStretch(0,1);self.middle.setColumnStretch(1,0 if compact else 1)
        self.bottom.setColumnStretch(0,1);self.bottom.setColumnStretch(1,0 if compact else 1)

    def resizeEvent(self,event):
        super().resizeEvent(event);self.arrange(self.viewport().width()<850)
        self.chart.setMinimumHeight(90 if self.viewport().height()<560 else 165)

    def update_data(self,summary,rows,previous,dates):
        self.data=summary;self.rows=rows;self.previous=previous;self.dates=dates
        for key,label in self.values.items():label.setText(str(summary[key]) if key=='count' else format_cop(summary[key]))
        percent=summary['change_percent']
        self.hints['total'].setText('Sin comparación: selecciona un período' if not dates[2] else 'Sin base anterior para comparar' if percent is None else f'{percent:+.1f} % frente al período anterior'.replace('.',','))
        self.hints['total'].setStyleSheet('font-size: 11px; color: '+('#137844' if percent is not None and percent>=0 else '#975d00' if percent is not None else '#657895')+';')
        self.hints['count'].setText('Operaciones vigentes');self.hints['average'].setText('Por venta · incluye envío cobrado');self.hints['pending'].setText(f"{summary['pending_count']} ventas pendientes")
        self.collection_bar.set_values(summary['received'],summary['pending'])
        self.collection_text.setText('Recibido: '+format_cop(summary['received'])+'\nPor cobrar: '+format_cop(summary['pending']))
        for key,label in self.cost_values.items():label.setText(format_cop(summary[key]))
        self.cost_hint.setText((f"Incluye comisión estimada de {summary['estimated_count']} ventas pendientes. " if summary['estimated_count'] else '')+'No incluye el costo de las máquinas; no es utilidad.')
        self.refresh_chart();self.refresh_ranking()

    def refresh_chart(self,*args):
        if self.data is None:return
        start,end,prior=self.dates;mode=self.scale.currentData()
        # Weekly charts remain readable on long date ranges by using monthly buckets.
        span=(end-start).days if start and end else 999
        if span>90 and mode=='week':mode='month'
        self.scale.setToolTip('En períodos mayores de 90 días se agrupa por mes para facilitar la lectura.' if span>90 else '')
        current=evolution(self.rows,start,end,mode)
        previous=comparative_evolution(self.previous,current,prior[0],prior[1]) if prior else []
        self.chart.set_values(current,previous)
        self.legend.setText('● Actual     ○ Anterior por tramo · Fechas e importes al pasar el cursor' if prior else '● Actual · Selecciona un período para comparar')

    def refresh_ranking(self,*args):
        group=self.kind.currentData();metric=self.rank_metric.currentData()
        entries=sorted(self.data[group] if self.data else [],key=lambda r:(-r[metric],r['code'],r['id']))[:5]
        largest=max((entry[metric] for entry in entries),default=1) or 1
        for i,(label,bar,value) in enumerate(self.rank_rows):
            visible=i<len(entries)
            for widget in (label,bar,value):widget.setVisible(visible)
            if visible:
                row=entries[i];label.setText(row['name']);label.setToolTip(row['code']+' · '+row['name']);bar.setValue(round(row[metric]*1000/largest));value.setText(str(row[metric]) if metric=='units' else format_cop(row[metric]));bar.setAccessibleName(row['name']+': '+value.text())
        self.rank_hint.setText('Sin ventas de '+('productos' if group=='products' else 'servicios')+' en este período.' if not entries else 'Cinco primeros · Productos y servicios se consultan por separado.')

    def clear_data(self):
        self.data=None;self.rows=[];self.previous=[]
        for label in list(self.values.values())+list(self.cost_values.values()):label.setText('—')
        for label in self.hints.values():label.clear()
        self.collection_text.setText('No disponible');self.collection_bar.set_values(0,0);self.cost_hint.clear();self.chart.set_values([],[]);self.refresh_ranking()
