"""Listado filtrable de ventas y acceso a sus cobros."""
from .attachments_dialog import attachment_button, with_attachment
from PySide6.QtCore import Signal,Qt,QDate
from datetime import date
from pathlib import Path
from dataclasses import replace
from calendar import monthrange
from PySide6.QtGui import QShortcut,QKeySequence,QColor
from PySide6.QtWidgets import QWidget,QFrame,QSizePolicy,QVBoxLayout,QHBoxLayout,QPushButton,QLineEdit,QComboBox,QCheckBox,QTableWidget,QTableWidgetItem,QHeaderView,QTabBar,QStackedWidget,QFileDialog,QMessageBox
from ..sales import SalesFilter
from ..sales_analytics import comparison_dates,summarize_sales
from .sales_dashboard import SalesDashboard
from ..storage import StorageError
from .sales_widgets import note,date_edit
from .style import format_cop
from .sale_dialog import SaleDialog
from .filter_popup import FilterPopup
from .sales_widgets import AmountEdit,error_text
from ..sales import money
from ..catalog import ValidationError
from .sale_detail_dialog import SaleDetailDialog
from .sales_report import build_sales_report
from .money_report import write_money_pdf


from .quick_entry_dialog import QuickEntryDialog, PendingEntries, quick_button

class SalesPage(QWidget):
    sales_changed=Signal()
    opening_failed=Signal(str)
    def __init__(self,catalog,settings,sales,parent=None,preferences=None):
        super().__init__(parent);self.catalog=catalog;self.settings=settings;self.sales=sales;self.dialog=None;self.rows=[]
        self.preferences=preferences
        root=QVBoxLayout(self);root.setContentsMargins(24,18,24,18)
        header=QHBoxLayout();header.addWidget(note('Ventas','heading'))
        header.addWidget(note('Registra tus ventas y confirma el dinero cuando llegue.'),1)
        self.quick=quick_button();header.addWidget(self.quick);self.quick.clicked.connect(lambda:self.open_quick())
        new=QPushButton('+ Nueva venta');new.setObjectName('primary');header.addWidget(new);root.addLayout(header)
        self.tabs=QTabBar();self.tabs.addTab('Resumen');self.tabs.addTab('Movimientos');self.tabs.setExpanding(False)
        self.tabs.setStyleSheet('QTabBar::tab { padding: 10px 16px; background: transparent; border-bottom: 2px solid transparent; } QTabBar::tab:selected { color: #315bea; border-bottom: 2px solid #315bea; }')
        root.addWidget(self.tabs)
        self.pages=QStackedWidget();self.dashboard=SalesDashboard();self.dashboard.movements_requested.connect(self.open_summary_movements);self.movements=QWidget();movement_box=QVBoxLayout(self.movements);movement_box.setContentsMargins(0,0,0,0)
        self.pages.addWidget(self.dashboard);self.pages.addWidget(self.movements);self.tabs.currentChanged.connect(self.pages.setCurrentIndex)
        summary=QHBoxLayout();summary.setSpacing(32)
        for title,attr,color in [('TOTAL DEL FILTRO','total_amount','#162e50'),('RECIBIDO','received_amount','#137844'),('POR COBRAR','pending_amount','#975d00')]:
            box=QVBoxLayout();box.setSpacing(4)
            caption=note(title);caption.setWordWrap(False);caption.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed);box.addWidget(caption)
            label=note('—','summaryAmount');label.setWordWrap(False);label.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed);label.setMinimumWidth(205);label.setStyleSheet('font-size: 25px; font-weight: 700; color: '+color+';')
            label.setToolTip('Importe bruto de ventas vigentes en esta vista. Incluye envío cobrado; no descuenta comisiones ni costos.')
            setattr(self,attr,label);box.addWidget(label);summary.addLayout(box)
        summary.addStretch();self.export_button=QPushButton('Exportar PDF');self.export_button.clicked.connect(self.export_pdf);summary.addWidget(self.export_button);movement_box.addLayout(summary)
        self.export_status=note('');self.export_status.hide();movement_box.addWidget(self.export_status)
        self.summary_caption=note('');root.addWidget(self.summary_caption)
        self.filter_group=QFrame();bar=QHBoxLayout(self.filter_group);bar.setContentsMargins(0,6,0,0)
        root.addWidget(self.filter_group)
        self.search=QLineEdit();self.search.setClearButtonEnabled(True);self.search.setPlaceholderText('Buscar cliente, código, producto o factura')
        self.state=QComboBox();self.state.addItem('Todos los estados',None);self.state.addItem('Pendiente de cobro',False);self.state.addItem('Recibido',True)
        self.account=QComboBox();self.account.addItem('Todas las cuentas',None)
        self.date_button=QPushButton('Todos los meses');self.more_button=QPushButton('Más filtros')
        for widget in (self.search,self.state,self.account,self.date_button,self.more_button):bar.addWidget(widget,1 if widget is self.search else 0)
        self.date_popup=FilterPopup('Fecha de venta',self)
        quick=QHBoxLayout();self.current_month_button=QPushButton('Este mes');self.quarter_button=QPushButton('Últimos 3 meses')
        quick.addWidget(self.current_month_button);quick.addWidget(self.quarter_button);self.date_popup.box.addLayout(quick)
        self.current_month_button.clicked.connect(self.current_month);self.quarter_button.clicked.connect(self.last_three_months)
        self.month=QComboBox();self.month.addItem('Todos los meses',0)
        for i,name in enumerate(('Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'),1):self.month.addItem(name,i)
        self.month.setCurrentIndex(self.month.findData(date.today().month))
        self.year=QComboBox();self._selected_year=date.today().year
        for year in range(self._selected_year,self._selected_year-6,-1):self.year.addItem(str(year),year)
        self.year.addItem('Más años anteriores…',None)
        self.month.setAccessibleName('Mes de venta');self.year.setAccessibleName('Año de venta')
        month_row=QHBoxLayout();month_row.addWidget(self.month);month_row.addWidget(self.year);self.date_popup.box.addLayout(month_row)
        self.use_dates=QCheckBox('Usar rango personalizado');self.date_popup.box.addWidget(self.use_dates)
        self.start=date_edit();self.start.setDate(self.start.date().addDays(1-self.start.date().day()));self.end=date_edit()
        self.date_fields=[note('Desde'),self.start,note('Hasta'),self.end]
        dates=QHBoxLayout()
        for widget in self.date_fields:dates.addWidget(widget);widget.setEnabled(False)
        self.date_popup.box.addLayout(dates);self.date_popup.finish()
        self.more_popup=FilterPopup('Más filtros',self)
        self.validity=QComboBox();self.validity.addItem('Vigentes',False);self.validity.addItem('Anuladas',True);self.validity.addItem('Todas las ventas',None)
        self.vat_filter=QComboBox();self.vat_filter.addItem('Todas',None);self.vat_filter.addItem('Con IVA',True);self.vat_filter.addItem('Sin IVA',False)
        self.withholding=QComboBox();self.withholding.addItem('Todas',None);self.withholding.addItem('Con retención',True);self.withholding.addItem('Sin retención',False)
        for title,widget in [('Ventas incluidas',self.validity),('Retención en la fuente',self.withholding),('IVA',self.vat_filter)]:
            self.more_popup.box.addWidget(note(title,'fieldHeading'));self.more_popup.box.addWidget(widget)
        self.more_popup.box.addWidget(note('Total de venta · COP','fieldHeading'))
        amounts=QHBoxLayout();self.min_total=AmountEdit();self.min_total.setPlaceholderText('Mínimo · opcional')
        self.max_total=AmountEdit();self.max_total.setPlaceholderText('Máximo · opcional')
        amounts.addWidget(self.min_total);amounts.addWidget(self.max_total);self.more_popup.box.addLayout(amounts)
        self.more_popup.finish()
        self.date_button.clicked.connect(lambda:self.date_popup.open_below(self.date_button))
        self.more_button.clicked.connect(lambda:self.more_popup.open_below(self.more_button))
        self.chips=QHBoxLayout();self.chip_buttons=[];root.addLayout(self.chips)
        self.min_total.textChanged.connect(self.refresh_sales);self.max_total.textChanged.connect(self.refresh_sales)
        self.month.currentIndexChanged.connect(self._month_changed);self.year.currentIndexChanged.connect(self._year_changed)
        self.use_dates.toggled.connect(self._custom_dates)
        self.table=QTableWidget(0,8);self.table.setHorizontalHeaderLabels(['Fecha','Cliente','Factura','Total · COP','Forma de pago','Cuenta','Estado','Acciones']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(44);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.setEditTriggers(QTableWidget.NoEditTriggers);movement_box.addWidget(self.table,1)
        self.table.verticalHeader().setDefaultSectionSize(66)
        for column,width in [(0,105),(2,65),(3,155),(4,135),(5,130),(6,105),(7,210)]:
            self.table.horizontalHeader().setSectionResizeMode(column,QHeaderView.Fixed);self.table.setColumnWidth(column,width)
        self.table.setShowGrid(False)
        self.quick_pending=PendingEntries(sales.connection,'sales');movement_box.addWidget(self.quick_pending);self.quick_pending.open_requested.connect(self.open_quick)
        self.error=note('','error');self.error.hide();root.addWidget(self.error);root.addWidget(self.pages,1);self.count=note('');movement_box.addWidget(self.count);detail=QPushButton('Ver detalle / Cobrar');movement_box.addWidget(detail)
        new.clicked.connect(self.open_new_sale);detail.clicked.connect(self.open_detail);self.table.cellDoubleClicked.connect(self.open_detail)
        for signal in (self.vat_filter.currentIndexChanged,self.validity.currentIndexChanged,self.search.textChanged,self.withholding.currentIndexChanged,self.state.currentIndexChanged,self.account.currentIndexChanged,self.use_dates.toggled,self.start.dateChanged,self.end.dateChanged):signal.connect(self.refresh_sales)
        self.new_shortcut=QShortcut(QKeySequence('Ctrl+N'),self);self.new_shortcut.setContext(Qt.WindowShortcut);self.new_shortcut.setEnabled(False);self.new_shortcut.activated.connect(self.open_new_sale)
        self.refresh_accounts();self.refresh_sales()

    def current_month(self):
        today=date.today()
        self.year.setCurrentIndex(self.year.findData(today.year));self.month.setCurrentIndex(self.month.findData(today.month))
        self.use_dates.setChecked(False);self._month_changed();self.date_popup.hide()

    def last_three_months(self):
        today=QDate.currentDate()
        for control in (self.month,self.use_dates,self.start,self.end):control.blockSignals(True)
        self.month.setCurrentIndex(0);self.use_dates.setChecked(True)
        self.start.setDate(QDate(today.year(),today.month(),1).addMonths(-2));self.end.setDate(today)
        for control in (self.month,self.use_dates,self.start,self.end):control.blockSignals(False)
        self._custom_dates(True);self.refresh_sales();self.date_popup.hide()

    def refresh_accounts(self):
        try:
            rows=self.settings.list_accounts(True)
            selected=self.account.currentData();self.account.blockSignals(True);self.account.clear();self.account.addItem('Todas las cuentas',None)
            for row in rows:self.account.addItem(row.name,row.id)
            self.account.setCurrentIndex(max(0,self.account.findData(selected)));self.account.blockSignals(False)
        except StorageError as e:self.error.setText(str(e));self.error.show()

    def _year_changed(self,*args):
        value=self.year.currentData()
        if value is None:
            oldest=min(self.year.itemData(i) for i in range(self.year.count()) if self.year.itemData(i) is not None)
            self.year.blockSignals(True);self.year.removeItem(self.year.count()-1)
            for year in range(oldest-1,max(1,oldest-5)-1,-1):self.year.addItem(str(year),year)
            if oldest-5>1:self.year.addItem('Más años anteriores…',None)
            self.year.setCurrentIndex(self.year.findData(self._selected_year));self.year.blockSignals(False)
            self.year.showPopup()
            return
        self._selected_year=value
        self._month_changed()

    def _month_changed(self,*args):
        if self.month.currentData():
            self.use_dates.blockSignals(True);self.use_dates.setChecked(False);self.use_dates.blockSignals(False)
            for widget in self.date_fields:widget.setEnabled(False)
        self.refresh_sales()

    def _custom_dates(self,checked):
        for widget in self.date_fields:widget.setEnabled(checked)
        if checked:
            self.month.blockSignals(True);self.month.setCurrentIndex(0);self.month.blockSignals(False)

    def open_summary_movements(self,pending=False):
        # Summary figures exclude cancelled sales; retain the other active filters.
        self.validity.blockSignals(True);self.validity.setCurrentIndex(self.validity.findData(False));self.validity.blockSignals(False)
        if pending:
            self.state.blockSignals(True);self.state.setCurrentIndex(self.state.findData(False));self.state.blockSignals(False)
        self.refresh_sales()
        self.tabs.setCurrentIndex(1)

    def refresh_sales(self,*args):
        try:
            self.quick_pending.refresh()
            if self.use_dates.isChecked() and self.start.date()>self.end.date():raise StorageError('La fecha inicial debe ser anterior o igual a la final.')
            month=self.month.currentData()
            start=date(self.year.currentData(),month,1) if month else (self.start.date().toPython() if self.use_dates.isChecked() else None)
            end=date(self.year.currentData(),month,monthrange(self.year.currentData(),month)[1]) if month else (self.end.date().toPython() if self.use_dates.isChecked() else None)
            filters=SalesFilter(start,end,self.account.currentData(),self.state.currentData(),self.search.text(),self.withholding.currentData(),self.validity.currentData(),self.vat_filter.currentData())
            prior_dates=comparison_dates(start,end,date.today(),bool(month))
            previous=self.sales.list_sales(replace(filters,start=prior_dates[0],end=prior_dates[1])) if prior_dates else []
            self.rows=self.sales.list_sales(filters)
            minimum=money(self.min_total.text()) if self.min_total.text().strip() else None
            maximum=money(self.max_total.text()) if self.max_total.text().strip() else None
            if minimum is not None and maximum is not None and minimum>maximum:raise StorageError('El total mínimo debe ser menor o igual al máximo.')
            self.rows=[row for row in self.rows if (minimum is None or row['total_cents']>=minimum) and (maximum is None or row['total_cents']<=maximum)]
            previous=[row for row in previous if (minimum is None or row['total_cents']>=minimum) and (maximum is None or row['total_cents']<=maximum)]
            lines=self.sales.list_lines([row['id'] for row in self.rows])
            self.dashboard.update_data(summarize_sales(self.rows,lines,previous),self.rows,previous,(start,min(end,date.today()) if end else None,prior_dates))
            active=[row for row in self.rows if not row['cancelled_at']]
            self.total_amount.setText(format_cop(sum(row['total_cents'] for row in active)))
            self.received_amount.setText(format_cop(sum(row['total_cents'] for row in active if row['received'])))
            self.pending_amount.setText(format_cop(sum(row['total_cents'] for row in active if not row['received'])))
            self._refresh_filter_labels()
            if end and end>date.today():self.summary_caption.setText(self.summary_caption.text()+f' Datos hasta {date.today():%d/%m/%Y}.')
            if prior_dates:self.summary_caption.setText(self.summary_caption.text()+f' Comparación: {prior_dates[0]:%d/%m/%Y} – {prior_dates[1]:%d/%m/%Y}.')
            descriptions={}
            for line in lines:descriptions.setdefault(line['sale_id'],[]).append(line['name'])
            self.table.setRowCount(len(self.rows))
            for i,s in enumerate(self.rows):
                for j,value in enumerate([s['sold_on'],s['customer_name'] or '—',s['invoice_ref'] or '—',format_cop(s['total_cents']),s['method_name'],s['account_name'],'Anulada' if s['cancelled_at'] else ('Recibido' if s['received'] else 'Pendiente')]):self.table.setItem(i,j,QTableWidgetItem(value))
                names=descriptions.get(s['id'],[])
                if names:
                    self.table.item(i,1).setText((s['customer_name'] or '—')+'\n'+names[0]+(f' +{len(names)-1}' if len(names)>1 else ''))
                    self.table.item(i,1).setToolTip('\n'.join(names))
                action=QPushButton('Confirmar cobro' if not s['received'] and not s['cancelled_at'] else 'Ver detalle')
                action.setStyleSheet('font-size: 12px; padding: 7px 10px;')
                action.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Fixed)
                action.setCursor(Qt.PointingHandCursor)
                action.setToolTip(action.text())
                if not s['received'] and not s['cancelled_at']:action.setObjectName('primary')
                action.clicked.connect(lambda checked=False,key=s['id'],collect=not s['received'] and not s['cancelled_at']:self.open_sale_detail(key,collect))
                actions=with_attachment(action,self.sales.connection,'sale',s['id'])
                actions.layout().setContentsMargins(4,0,4,0)
                actions.layout().setAlignment(Qt.AlignVCenter)
                self.table.setCellWidget(i,7,actions)
                actions.ensurePolished()
                # Qt removes the cell's horizontal padding from the widget area.
                self.table.setColumnWidth(7,max(self.table.columnWidth(7),actions.sizeHint().width()+24))
                status_item=self.table.item(i,6)
                status_item.setForeground(QColor('#758198' if s['cancelled_at'] else '#137844' if s['received'] else '#975d00'))
                badge=note(status_item.text());badge.setAlignment(Qt.AlignCenter);badge.setWordWrap(False)
                badge.setStyleSheet('font-size: 12px; border-radius: 10px; padding: 4px 6px; color: '+('#758198' if s['cancelled_at'] else '#137844' if s['received'] else '#975d00')+'; background: '+('#edf0f6' if s['cancelled_at'] else '#ddf5e8' if s['received'] else '#fff0cd')+';')
                holder=QWidget();layout=QHBoxLayout(holder);layout.setContentsMargins(4,0,4,0);layout.addWidget(badge,0,Qt.AlignVCenter)
                holder.setAttribute(Qt.WA_TransparentForMouseEvents);self.table.setCellWidget(i,6,holder)
                self.table.item(i,3).setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.count.setText(f'Mostrando {len(self.rows)} ventas · Totales según los filtros activos');self.error.clear();self.error.hide()
        except (StorageError,ValidationError) as e:
            self.dashboard.clear_data();self.rows=[];self.table.setRowCount(0);self.count.setText('No disponible');self.error.setText(error_text(e));self.error.show()
            for label in (self.total_amount,self.received_amount,self.pending_amount):label.setText('—')
            self._refresh_filter_labels()

    def export_pdf(self):
        self.export_status.hide()
        self.refresh_sales()
        if self.error.text():return
        filters=[('Fecha de venta',self.date_button.text()),('Estado de cobro',self.state.currentText()),
                 ('Cuenta',self.account.currentText()),('Ventas incluidas',self.validity.currentText()),
                 ('IVA',self.vat_filter.currentText()),('Retención',self.withholding.currentText()),('Búsqueda',self.search.text() or 'Sin búsqueda'),
                 ('Total mínimo · COP',self.min_total.text() or 'Sin mínimo'),
                 ('Total máximo · COP',self.max_total.text() or 'Sin máximo')]
        html=build_sales_report(self.rows,filters)
        path,_=QFileDialog.getSaveFileName(self,'Exportar ventas a PDF',
            f'Nimbo-ventas-{date.today()}.pdf','Documento PDF (*.pdf)')
        if not path:return
        try:
            if not path.lower().endswith('.pdf'):
                path+='.pdf'
                if Path(path).exists() and QMessageBox.question(self,'Reemplazar informe',
                    'Ya existe este PDF. ¿Quieres reemplazarlo?',QMessageBox.Yes|QMessageBox.No,
                    QMessageBox.No)!=QMessageBox.Yes:return
            write_money_pdf(path,html,title='Nimbo · Ventas')
            self.export_status.setText('PDF guardado en: '+path);self.export_status.show()
        except (OSError,ValueError,RuntimeError) as exc:
            self.error.setText(error_text(exc));self.error.show()

    def _clear_amounts(self):
        self.min_total.clear();self.max_total.clear()

    def _clear_dates(self):
        self.use_dates.setChecked(False);self.month.setCurrentIndex(0)

    def _refresh_filter_labels(self):
        self.date_button.setText((self.start.date().toString('dd/MM/yyyy')+' – '+self.end.date().toString('dd/MM/yyyy')) if self.use_dates.isChecked() else
            (self.month.currentText()+' '+str(self.year.currentData()) if self.month.currentData() else 'Todos los meses'))
        self.summary_caption.setText('Ventas vigentes · '+self.date_button.text()+' · según los filtros seleccionados.')
        extra=int(self.vat_filter.currentData() is not None)+int(self.validity.currentData() is not None)+int(self.withholding.currentData() is not None)+int(bool(self.min_total.text().strip() or self.max_total.text().strip()))
        self.more_button.setText('Más filtros'+(' · '+str(extra) if extra else ''))
        while self.chips.count():
            item=self.chips.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.chip_buttons=[]
        selections=[]
        for combo in (self.validity,self.withholding,self.vat_filter,self.state,self.account):
            if combo.currentData() is not None:
                selections.append((combo.currentText(),lambda checked=False,c=combo:c.setCurrentIndex(c.findData(None))))
        if self.month.currentData() or self.use_dates.isChecked():selections.append(('Fecha: '+self.date_button.text(),self._clear_dates))
        if self.min_total.text().strip() or self.max_total.text().strip():selections.append(('Total: '+(self.min_total.text() or '0')+' – '+(self.max_total.text() or 'sin máximo'),self._clear_amounts))
        for text,clear in selections:
            button=QPushButton(text+' ×');button.setToolTip('Quitar filtro: '+text)
            button.setStyleSheet('QPushButton { background: #e5ecff; color: #284bb5; border: 0; border-radius: 12px; padding: 5px 10px; }')
            button.clicked.connect(clear);self.chips.addWidget(button);self.chip_buttons.append(button)
        self.chips.addStretch()

    def changed(self,*args):self.refresh_sales();self.sales_changed.emit()

    def open_quick(self,entry_id=None):
        if self.dialog and self.dialog.isVisible():self.dialog.raise_();return
        self.dialog=QuickEntryDialog(self.sales.connection,'sales',self.window(),self.preferences,entry_id)
        self.dialog.saved.connect(self.changed);self.dialog.show()

    def open_new_sale(self):
        if self.dialog and self.dialog.isVisible():self.dialog.raise_();return
        try:
            self.dialog=SaleDialog(self.catalog,self.settings,self.sales,self.window(),preferences=self.preferences);self.dialog.saved.connect(self.changed);self.dialog.show()
        except StorageError as e:
            self.error.setText(str(e));self.error.show();self.opening_failed.emit(str(e))

    def open_detail(self,*args):
        if self.dialog and self.dialog.isVisible():self.dialog.raise_();return
        row=self.table.currentRow()
        if not 0<=row<len(self.rows):return
        self.open_sale_detail(self.rows[row]['id'])

    def open_sale_detail(self,key,collect=False):
        if self.dialog and self.dialog.isVisible():self.dialog.raise_();return
        try:
            if collect:
                from .receipt_dialog import ReceiptDialog
                self.dialog=ReceiptDialog(key,self.settings,self.sales,self.window())
            else:self.dialog=SaleDetailDialog(key,self.settings,self.sales,self.window())
            self.dialog.saved.connect(self.changed);self.dialog.show()
        except StorageError as e:self.error.setText(str(e));self.error.show();self.opening_failed.emit(str(e))

    def show_period(self,start=None,end=None):
        controls=(self.month,self.use_dates,self.start,self.end,self.search,self.account,self.state,self.validity,self.withholding,self.vat_filter,self.min_total,self.max_total)
        for control in controls:control.blockSignals(True)
        self.month.setCurrentIndex(0);self.use_dates.setChecked(start is not None)
        if start is not None:self.start.setDate(QDate(start.year,start.month,start.day));self.end.setDate(QDate(end.year,end.month,end.day))
        self.search.clear();self.min_total.clear();self.max_total.clear()
        for combo in (self.account,self.state,self.validity,self.withholding,self.vat_filter):combo.setCurrentIndex(0)
        for control in controls:control.blockSignals(False)
        self._custom_dates(start is not None);self.tabs.setCurrentIndex(1);self.refresh_accounts();self.refresh_sales()

    def show_pending(self):
        self.tabs.setCurrentIndex(1)
        self._clear_amounts()
        self.month.setCurrentIndex(0)
        self.validity.setCurrentIndex(0);self.search.clear();self.withholding.setCurrentIndex(0);self.vat_filter.setCurrentIndex(0);self.account.setCurrentIndex(0);self.use_dates.setChecked(False);self.state.setCurrentIndex(1);self.refresh_sales()
