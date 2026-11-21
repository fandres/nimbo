"""Inicio: resumen honesto del alcance disponible y acceso al catálogo."""
from PySide6.QtCore import QDate, QLocale, Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QFrame, QScrollArea, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QSizePolicy,
)

from ..repository import StorageError
from .icons import icon
from .style import PALETTE, HOME_ACTION_COLORS, format_cop
from datetime import date


def label(text, name='muted'):
    result = QLabel(text)
    result.setObjectName(name)
    result.setWordWrap(True)
    result.setTextFormat(Qt.PlainText)
    return result


def card(title=None, hero=False):
    frame = QFrame()
    frame.setObjectName('heroCard' if hero else 'homeCard')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(6)
    if title:
        layout.addWidget(label(title, 'heroEyebrow' if hero else 'cardTitle'))
    return frame, layout


class HomeAction(QPushButton):
    """A keyboard-accessible button whose size follows its card contents."""
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def sizeHint(self):
        return self.layout().sizeHint() if self.layout() else super().sizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize() if self.layout() else super().minimumSizeHint()


class HomePage(QWidget):
    open_catalog=Signal()
    new_sale_requested=Signal()
    pending_requested=Signal()
    new_purchase_requested=Signal()
    new_expense_requested=Signal()
    sales_period_requested=Signal(object,object)
    expenses_period_requested=Signal(object,object)
    all_sales_requested=Signal()
    pending_expenses_requested=Signal()
    money_requested=Signal()
    accounts_requested=Signal()
    sale_requested=Signal(int,bool)

    def __init__(self,repository,parent=None,sales=None,purchases_available=False,expenses_available=False):
        super().__init__(parent);self.repository=repository;self.sales=sales;self.snapshot=None;self._compact=None
        from .home_chart import HomeChart
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.NoFrame)
        content=QWidget();content.setObjectName('homeContent');self.scroll.setWidget(content);root.addWidget(self.scroll)
        layout=QVBoxLayout(content);layout.setContentsMargins(24,18,24,14);layout.setSpacing(14)
        self.header=QGridLayout();heading=QWidget();heading_box=QVBoxLayout(heading);heading_box.setContentsMargins(0,0,0,0)
        self.date_label=label('');heading_box.addWidget(self.date_label);heading_box.addWidget(label('Tu negocio, de un vistazo','homeTitle'));self.heading=heading
        self.actions=QWidget();actions=QHBoxLayout(self.actions);actions.setContentsMargins(0,0,0,0)
        self.new_purchase_button=QPushButton('+ Nueva compra');self.new_expense_button=QPushButton('+ Nuevo gasto');self.new_sale_button=QPushButton('+ Nueva venta')
        self.new_sale_button.setObjectName('primary')
        self.new_purchase_button.setStyleSheet('QPushButton {color:#7040b0;background:#f4eefb;} QPushButton:hover {background:#e8daf7;}')
        self.new_expense_button.setStyleSheet('QPushButton {color:#99621e;background:#fff5e9;} QPushButton:hover {background:#ffead0;}')
        self.future_actions=[]
        for button,signal,enabled in [(self.new_purchase_button,self.new_purchase_requested,purchases_available),(self.new_expense_button,self.new_expense_requested,expenses_available),(self.new_sale_button,self.new_sale_requested,sales is not None)]:
            button.setMinimumHeight(40);button.setCursor(Qt.PointingHandCursor);button.clicked.connect(signal.emit);button.setEnabled(enabled);actions.addWidget(button)
            if not enabled:self.future_actions.append(button)
        layout.addLayout(self.header)
        self.metrics=QGridLayout();self.metrics.setSpacing(12);self.metric_cards=[]
        for key,title,callback in [('sales','VENTAS DEL MES',self.open_month_sales),('expenses','GASTOS DEL MES',self.open_month_expenses),('pending','POR COBRAR',self.pending_requested.emit),('cash','TU DINERO',self.money_requested.emit)]:
            frame=HomeAction();frame.setObjectName('homeMetric');frame.setCursor(Qt.PointingHandCursor);frame.clicked.connect(callback)
            box=QVBoxLayout(frame);box.setContentsMargins(16,14,16,14);box.setSpacing(6)
            caption=label(title);value=label('—','homeMetricValue');detail=label('');change=label('')
            for widget in (caption,value,change,detail):box.addWidget(widget);widget.setAttribute(Qt.WA_TransparentForMouseEvents)
            value.setStyleSheet('font-size:25px;font-weight:700;color:'+('#975d00' if key=='pending' else '#183052')+';')
            frame.setAccessibleName(title);setattr(self,key+'_caption',caption);setattr(self,key+'_value',value);setattr(self,key+'_detail',detail);setattr(self,key+'_change',change)
            self.metric_cards.append(frame)
        self.sales_total=self.sales_value;self.pending_total=self.pending_detail;self.cash_balance=self.cash_value;self.cash_notice=self.cash_detail
        layout.addLayout(self.metrics)
        self.middle=QGridLayout();self.middle.setSpacing(14)
        self.chart_card,chart_box=card();chart_header=QHBoxLayout();chart_header.addWidget(label('Ventas por mes','cardTitle'),1);self.chart_notice=label('');chart_header.addWidget(self.chart_notice);chart_box.addLayout(chart_header)
        self.chart=HomeChart();self.chart.period_requested.connect(self.sales_period_requested.emit);chart_box.addWidget(self.chart,1)
        self.attention,self.attention_box=card('Para atender');self.attention_rows=QVBoxLayout();self.attention_box.addLayout(self.attention_rows);self.attention_box.addStretch()
        layout.addLayout(self.middle,1)
        self.recent_sales,recent=card();recent_header=QHBoxLayout();recent_header.addWidget(label('Últimas ventas','cardTitle'),1)
        self.all_sales_button=QPushButton('Ver todas →');self.all_sales_button.setObjectName('quietAction');self.all_sales_button.clicked.connect(self.all_sales_requested.emit);recent_header.addWidget(self.all_sales_button);recent.addLayout(recent_header)
        self.recent_rows=QVBoxLayout();recent.addLayout(self.recent_rows);self.recent_text=label('Aún no has registrado ventas.');recent.addWidget(self.recent_text)
        layout.addWidget(self.recent_sales)
        catalog=QHBoxLayout();catalog.addWidget(label('Catálogo:'));self.products_count=label('—');self.services_count=label('—')
        for widget in (self.products_count,label('productos ·'),self.services_count,label('servicios')):catalog.addWidget(widget)
        self.catalog_button=QPushButton('Ver catálogo →');self.catalog_button.setObjectName('quietAction');self.catalog_button.clicked.connect(self.open_catalog.emit);catalog.addWidget(self.catalog_button);catalog.addStretch();layout.addLayout(catalog)
        self.error_label=label('','error');self.error_label.hide();self.retry_button=QPushButton('Reintentar');self.retry_button.hide();self.retry_button.clicked.connect(self.refresh_summary);layout.addWidget(self.error_label);layout.addWidget(self.retry_button)
        self.action_cards=[self.new_sale_button,self.new_purchase_button,self.new_expense_button,self.metric_cards[2]]
        self._arrange(False)
        self.refresh_timer=QTimer(self);self.refresh_timer.setInterval(60000);self.refresh_timer.timeout.connect(lambda:self.refresh_summary() if self.isVisible() else None);self.refresh_timer.start()

    def _arrange(self,compact):
        if compact==self._compact:return
        self._compact=compact
        for grid in (self.header,self.metrics,self.middle):
            while grid.count():grid.takeAt(0)
            for col in range(4):grid.setColumnStretch(col,0)
        self.header.addWidget(self.heading,0,0);self.header.addWidget(self.actions,1 if compact else 0,0 if compact else 1);self.header.setColumnStretch(0,1)
        cols=2 if compact else 4
        for i,card_widget in enumerate(self.metric_cards):self.metrics.addWidget(card_widget,i//cols,i%cols)
        for col in range(cols):self.metrics.setColumnStretch(col,1)
        self.middle.addWidget(self.chart_card,0,0);self.middle.addWidget(self.attention,1 if compact else 0,0 if compact else 1);self.middle.setColumnStretch(0,3)
        if not compact:self.middle.setColumnStretch(1,2)

    def resizeEvent(self,event):super().resizeEvent(event);self._arrange(self.width()<1000)

    def open_month_sales(self):
        if self.snapshot:self.sales_period_requested.emit(self.snapshot['start'],self.snapshot['today'])
    def open_month_expenses(self):
        if self.snapshot:self.expenses_period_requested.emit(self.snapshot['start'],self.snapshot['today'])

    @staticmethod
    def clear_rows(layout):
        while layout.count():
            item=layout.takeAt(0)
            if item.widget():item.widget().hide();item.widget().deleteLater()

    def attention_row(self,title,detail,action,callback,primary=False):
        frame=QFrame();frame.setObjectName('homeAttention');row=QHBoxLayout(frame);row.setContentsMargins(0,8,0,8)
        text=QVBoxLayout();text.addWidget(label(title,'fieldHeading'));text.addWidget(label(detail));row.addLayout(text,1)
        button=QPushButton(action);button.setCursor(Qt.PointingHandCursor)
        if primary:button.setObjectName('primary')
        button.clicked.connect(callback);row.addWidget(button);self.attention_rows.addWidget(frame)

    def change_text(self,key,current,previous):
        from ..home_dashboard import percentage_change
        value=percentage_change(current,previous);widget=getattr(self,key+'_change')
        if value is None:widget.setText('Sin base de comparación');widget.setStyleSheet('color:#64748b;');return
        good=value>0 if key=='sales' else value<0
        color='#137844' if good else '#b4232d' if value else '#64748b'
        widget.setText(('▲ ' if value>0 else '▼ ' if value<0 else '')+str(abs(value)).replace('.',',')+' %');widget.setStyleSheet('color:'+color+';font-weight:700;')

    def refresh_summary(self):
        from ..home_dashboard import home_snapshot
        from .expense_filters import MONTHS
        from calendar import monthrange
        self.date_label.setText(QLocale(QLocale.Spanish,QLocale.Colombia).toString(QDate.currentDate(),"dddd d 'de' MMMM"))
        try:data=home_snapshot(self.repository,self.sales)
        except StorageError as exc:
            self.snapshot=None
            for key in ('sales','expenses','pending','cash'):
                getattr(self,key+'_value').setText('No disponible');getattr(self,key+'_detail').clear();getattr(self,key+'_change').clear()
            self.products_count.setText('—');self.services_count.setText('—');self.chart.set_values([])
            self.clear_rows(self.attention_rows);self.clear_rows(self.recent_rows);self.recent_text.setText('No se pudieron consultar las ventas.');self.recent_text.show()
            self.error_label.setText(str(exc));self.error_label.show();self.retry_button.show();return
        self.snapshot=data;self.error_label.hide();self.error_label.clear();self.retry_button.hide()
        month=MONTHS[data['today'].month-1];self.sales_caption.setText('VENTAS DE '+month.upper());self.expenses_caption.setText('GASTOS DE '+month.upper())
        self.sales_value.setText(format_cop(data['sales_total']));self.expenses_value.setText(format_cop(data['expenses_total']));self.pending_value.setText(format_cop(data['pending_total']));self.cash_value.setText(format_cop(data['money']['available']))
        previous=f"vs {data['previous_start']:%d/%m}–{data['previous_end']:%d/%m}: "
        self.sales_detail.setText(f"{data['sales_count']} ventas · "+previous+format_cop(data['sales_previous']))
        self.expenses_detail.setText(previous+format_cop(data['expenses_previous'])+(' · Incluye estimaciones' if data['expenses_estimated'] else ''))
        self.change_text('sales',data['sales_total'],data['sales_previous']);self.change_text('expenses',data['expenses_total'],data['expenses_previous'])
        self.pending_detail.setText(f"{len(data['pending'])} pendientes · Todos los meses")
        missing=data['money']['missing'];self.cash_detail.setText(f'Saldo parcial · {missing} cuentas sin configurar' if missing else 'Efectivo y bancos · disponible hoy')
        for frame,text in zip(self.metric_cards,['Ventas vigentes por fecha de venta. Incluye IVA y envío cobrado.','Gastos registrados, incluidos pendientes y comisiones. No equivale a pagos realizados.','Total bruto de todas las ventas vigentes pendientes de cobro.','Saldos iniciales más entradas menos salidas registradas. Excluye tarjetas y retenciones. No es utilidad.']):frame.setToolTip(text)
        configured=any(a['configured'] for a in data['money']['balances'] if not a['is_card'] and a['kind']!='withholding')
        if missing and not configured:self.cash_value.setText('Sin configurar')
        self.cash_detail.setStyleSheet('color:#875500;background:#fff3d6;padding:6px;border-radius:6px;' if missing else '')
        if missing:
            self.metric_cards[3].setToolTip('Falta configurar el saldo inicial de '+str(missing)+' cuenta(s). Ve a Dinero → Cuentas y haz doble clic en la cuenta. Indica cuánto dinero había al comienzo de la fecha elegida; puede ser cero. Las cuentas pendientes no se incluyen en este saldo.')
        self.chart_notice.setText(f"{month}: {data['today'].day} de {monthrange(data['today'].year,data['today'].month)[1]} días");self.chart.set_values(data['months'])
        self.products_count.setText(str(data['products']));self.services_count.setText(str(data['services']))
        self.clear_rows(self.attention_rows)
        if data['pending']:
            sale=data['pending'][0]
            self.attention_row('Venta '+(sale['invoice_ref'] or '#'+str(sale['id']))+' por cobrar',f"{sale['method_name']} · {sale['sold_on']} · {format_cop(sale['total_cents'])}",'Cobrar',lambda checked=False,key=sale['id']:self.sale_requested.emit(key,True),True)
        if data['unpaid']:
            detail=format_cop(data['unpaid_total'])
            if data['next_due']:detail+=' · Vencimiento: '+data['next_due']
            self.attention_row(f"{len(data['unpaid'])} gastos por pagar",detail,'Ver',self.pending_expenses_requested.emit)
        if missing:self.attention_row('Configura el saldo inicial',f'{missing} cuentas pendientes · Indica cuánto dinero había al comenzar','Configurar',self.accounts_requested.emit)
        if data['reminders']:self.attention_row('Revisa tus tarjetas',' · '.join(r['text'] for r in data['reminders']),'Ver',self.money_requested.emit)
        if not self.attention_rows.count():self.attention_rows.addWidget(label('No hay asuntos pendientes por atender.'))
        self.clear_rows(self.recent_rows);self.recent_text.setVisible(not data['recent']);self.recent_text.setText('Aún no has registrado ventas.')
        for sale in data['recent']:
            button=HomeAction();button.setObjectName('homeRecent');button.setCursor(Qt.PointingHandCursor)
            row=QHBoxLayout(button);row.setContentsMargins(8,8,8,8)
            values=[sale['sold_on'],'Venta '+(sale['invoice_ref'] or '#'+str(sale['id'])),sale['method_name'],'Recibido' if sale['received'] else 'Pendiente',format_cop(sale['total_cents'])]
            for i,text in enumerate(values):
                cell=label(text);cell.setAttribute(Qt.WA_TransparentForMouseEvents);row.addWidget(cell,1 if i in (1,2) else 0)
                if i==3:cell.setStyleSheet('color:'+('#137844' if sale['received'] else '#975d00')+';background:'+('#ddf5e8' if sale['received'] else '#fff0cd')+';border-radius:9px;padding:4px 8px;')
            button.setAccessibleName(' · '.join(values));button.setToolTip(sale['customer_name']+' · Abrir detalle');button.clicked.connect(lambda checked=False,key=sale['id']:self.sale_requested.emit(key,False));self.recent_rows.addWidget(button)
