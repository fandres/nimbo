"""Listado de pedidos registrados: no es inventario ni flujo de caja."""
from .attachments_dialog import attachment_button, with_attachment
from PySide6.QtCore import Qt, Signal, QSize
from datetime import date
from html import escape
from calendar import monthrange
from decimal import Decimal, ROUND_HALF_UP
from PySide6.QtGui import QShortcut, QKeySequence, QColor
from PySide6.QtWidgets import QWidget,QFrame,QVBoxLayout,QHBoxLayout,QPushButton,QLineEdit,QComboBox,QCheckBox,QSizePolicy,QTreeWidgetItem,QHeaderView,QAbstractItemView
from ..purchases import PurchasesFilter, CATEGORIES, categories_for
from ..purchases_repository import draft_from_record
from ..purchase_allocation import purchase_progress, line_unit_costs
from ..storage import StorageError
from .purchase_dialog import PurchaseDialog
from .purchase_tree import PurchaseTree
from .filter_popup import FilterPopup
from .preferences import DisplayPreferences
from .purchase_receipt_dialog import PurchaseReceiptDialog
from ..purchase_receipts_repository import PurchaseReceiptsRepository
from .sales_widgets import note,date_edit
from .style import format_cop


MONTHS=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']


class PurchasesPage(QWidget):
    purchases_changed=Signal()
    opening_failed=Signal(str)

    def __init__(self,catalog,purchases,parent=None,preferences=None):
        super().__init__(parent); self.catalog=catalog; self.purchases=purchases; self.rows=[]; self.dialog=None
        self.preferences=preferences if preferences is not None else DisplayPreferences()
        self.receipts=PurchaseReceiptsRepository(purchases.connection)
        root=QVBoxLayout(self); root.setContentsMargins(24,18,24,18)
        header=QHBoxLayout();header.addWidget(note('Compras','heading'))
        header.addWidget(note('Mercancía y costos registrados. Las cantidades todavía no representan inventario disponible.'),1)
        new=QPushButton('+ Nueva compra');new.setObjectName('newPurchase');header.addWidget(new);root.addLayout(header)
        capital=QHBoxLayout();capital.setContentsMargins(0,12,0,12)
        capital_box=QVBoxLayout();capital_box.addWidget(note('INVERSIÓN TOTAL EN COMPRAS · COP'))
        self.capital_amount=note('—','summaryAmount');self.capital_amount.setStyleSheet('font-size: 28px; font-weight: 700; color: #162e50;')
        capital_box.addWidget(self.capital_amount);capital.addLayout(capital_box,1)
        self.monthly_summary=QWidget();monthly_box=QVBoxLayout(self.monthly_summary);monthly_box.setContentsMargins(16,0,16,0)
        self.monthly_heading=note('');monthly_box.addWidget(self.monthly_heading)
        self.monthly_amount=note('—','summaryAmount');self.monthly_amount.setStyleSheet('font-size: 25px; font-weight: 700; color: #315be7;');monthly_box.addWidget(self.monthly_amount)
        self.monthly_summary.setToolTip('Pedidos vigentes del mes actual, incluida la mercancía y los gastos registrados. Puede incluir costos provisionales. No representa pagos realizados.')
        capital.addWidget(self.monthly_summary,1)
        self.capital_hint=note('');capital.addWidget(self.capital_hint,1);root.addLayout(capital)
        self.filter_group=QFrame();filters=QHBoxLayout(self.filter_group);filters.setContentsMargins(0,0,0,0)
        root.addWidget(self.filter_group)
        self.search=QLineEdit();self.search.setClearButtonEnabled(True);self.search.setPlaceholderText('Buscar proveedor, alias, referencia, código o producto')
        self.validity=QComboBox();self.validity.addItem('Vigentes',False);self.validity.addItem('Anuladas',True);self.validity.addItem('Todas',None)
        self.date_button=QPushButton();self.more_button=QPushButton('Más filtros')
        for widget in (self.search,self.validity,self.date_button,self.more_button):filters.addWidget(widget,1 if widget is self.search else 0)
        self.date_popup=FilterPopup('Fecha de compra',self)
        self.month=QComboBox();self.month.addItem('Todo el año',0)
        for i,name in enumerate(MONTHS,1):self.month.addItem(name,i)
        self.month.addItem('Todos los años',-1)
        self.year=QComboBox();self._selected_year=date.today().year
        for year in range(self._selected_year,self._selected_year-6,-1):self.year.addItem(str(year),year)
        self.year.addItem('Más años anteriores…',None)
        self.month.setAccessibleName('Mes de compra');self.year.setAccessibleName('Año de compra')
        months=QHBoxLayout();months.addWidget(self.month);months.addWidget(self.year);self.date_popup.box.addLayout(months)
        self.use_dates=QCheckBox('Usar rango personalizado');self.date_popup.box.addWidget(self.use_dates)
        self.start=date_edit();self.start.setDate(self.start.date().addDays(1-self.start.date().day()));self.end=date_edit()
        self.date_fields=[note('Desde'),self.start,note('Hasta'),self.end]
        dates=QHBoxLayout()
        for widget in self.date_fields:dates.addWidget(widget);widget.setEnabled(False)
        self.date_popup.box.addLayout(dates);self.date_popup.finish()
        self.more_popup=FilterPopup('Más filtros de compras',self)
        self.state=QComboBox();self.state.addItem('Todos los costos',None);self.state.addItem('Por completar',False);self.state.addItem('Costos completos',True)
        self.received_filter=QComboBox()
        for label,value in [('Todas las recepciones',None),('Pendientes de recepción',False),('Recibidos',True)]:self.received_filter.addItem(label,value)
        self.progress_filter=QComboBox()
        for label,value in [('Todos los estados',None),('Costos pendientes','costs_pending'),('Envío pendiente','shipping_pending'),
                            ('Nacionalización pendiente','nationalization_pending'),('Falta distribuir gastos','allocation_pending'),('Completos','complete')]:
            self.progress_filter.addItem(label,value)
        for title,widget in [('Costos',self.state),('Avance del pedido',self.progress_filter),('Recepción',self.received_filter)]:
            self.more_popup.box.addWidget(note(title,'fieldHeading'));self.more_popup.box.addWidget(widget)
        clear=QPushButton('Limpiar filtros adicionales');clear.clicked.connect(self._clear_extra_filters);self.more_popup.box.addWidget(clear)
        self.more_popup.finish()
        self.date_button.clicked.connect(lambda:self.date_popup.open_below(self.date_button))
        self.more_button.clicked.connect(lambda:self.more_popup.open_below(self.more_button))
        self.month.currentIndexChanged.connect(self._month_changed)
        self.year.currentIndexChanged.connect(self._year_changed)
        self.use_dates.toggled.connect(self._custom_dates)

        shortcuts=QHBoxLayout();shortcuts.addWidget(note('Atajos:'))
        self.pending_count=QPushButton();self.receipt_count=QPushButton()
        self.pending_count.setToolTip('Ver pedidos vigentes con costos pendientes en el período y búsqueda actuales')
        self.receipt_count.setToolTip('Ver pedidos vigentes pendientes de recepción en el período y búsqueda actuales')
        for widget,bg,fg in [(self.pending_count,'#fff1d1','#925400'),(self.receipt_count,'#e3eaff','#284bb5')]:
            widget.setStyleSheet('QPushButton { background: '+bg+'; color: '+fg+'; border: 0; border-radius: 14px; padding: 6px 12px; }')
            shortcuts.addWidget(widget)
        shortcuts.addStretch();root.addLayout(shortcuts)
        self.pending_count.clicked.connect(lambda:self._quick_filter('costs'))
        self.receipt_count.clicked.connect(lambda:self._quick_filter('receipt'))
        self.table=PurchaseTree();self.table.setColumnCount(7)
        self.table.setHeaderLabels(['Pedido / producto','Cantidad','Compra/u · COP','Con gastos/u · COP','Estado','Total del pedido','Acciones'])
        self.table.setWordWrap(True);self.table.setTextElideMode(Qt.ElideNone)
        self.table.setRootIsDecorated(True);self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(0,QHeaderView.Stretch)
        for col,width in enumerate((85,135,140,210,160,260),1):
            self.table.header().setSectionResizeMode(col,QHeaderView.Interactive);self.table.setColumnWidth(col,width)
        self.table.setStyleSheet('QTreeWidget { selection-background-color: #e5edff; selection-color: #162e50; background: white; border: 1px solid #e1e7f1; border-radius: 12px; } QTreeWidget::item { padding: 8px 4px; border-bottom: 1px solid #edf0f6; } QTreeWidget::item:selected { background: #e5edff; color: #162e50; }')
        root.addWidget(self.table,1)
        self.error=note('','error');root.addWidget(self.error);self.count=note('');root.addWidget(self.count)
        new.clicked.connect(self.open_new_purchase);self.table.itemDoubleClicked.connect(self.open_detail)
        for signal in (self.search.textChanged,self.state.currentIndexChanged,self.validity.currentIndexChanged,self.use_dates.toggled,self.start.dateChanged,self.end.dateChanged,self.progress_filter.currentIndexChanged,self.received_filter.currentIndexChanged): signal.connect(self.refresh_purchases)
        self.new_shortcut=QShortcut(QKeySequence('Ctrl+N'),self); self.new_shortcut.setContext(Qt.WindowShortcut)
        self.new_shortcut.setEnabled(False); self.new_shortcut.activated.connect(self.open_new_purchase)
        self.refresh_purchases()

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
        self.use_dates.blockSignals(True);self.use_dates.setChecked(False);self.use_dates.blockSignals(False)
        for widget in self.date_fields:widget.setEnabled(False)
        self.year.setEnabled(self.month.currentData()!=-1)
        self.refresh_purchases()

    def _custom_dates(self,checked):
        for widget in self.date_fields: widget.setEnabled(checked)
        if checked:
            self.month.blockSignals(True); self.month.setCurrentIndex(0); self.month.blockSignals(False)
            self.year.setEnabled(True)

    def _clear_extra_filters(self):
        for combo in (self.state,self.progress_filter,self.received_filter):
            combo.blockSignals(True);combo.setCurrentIndex(0);combo.blockSignals(False)
        self.refresh_purchases()

    def _quick_filter(self,kind):
        for combo,value in ((self.validity,False),(self.state,None),
                            (self.progress_filter,'costs_pending' if kind=='costs' else None),
                            (self.received_filter,False if kind=='receipt' else None)):
            combo.blockSignals(True);combo.setCurrentIndex(combo.findData(value));combo.blockSignals(False)
        self.refresh_purchases()

    def _filter_labels(self):
        self.date_button.setText((self.start.date().toString('dd/MM/yyyy')+' – '+self.end.date().toString('dd/MM/yyyy')) if self.use_dates.isChecked() else
            ('Todos los años' if self.month.currentData()==-1 else self.month.currentText()+' '+str(self.year.currentData())))
        selected=[combo.currentText() for combo in (self.state,self.progress_filter,self.received_filter) if combo.currentData() is not None]
        self.more_button.setText('Más filtros'+(' · '+str(len(selected)) if selected else ''))
        self.more_button.setToolTip(' · '.join(selected) or 'Costos, avance y recepción')

    @staticmethod
    def _badge(text,bg,fg):
        label=note(text);label.setWordWrap(False)
        label.setStyleSheet('background: '+bg+'; color: '+fg+'; border-radius: 10px; padding: 4px 8px; font-size: 12px; font-weight: 600;')
        label.setSizePolicy(QSizePolicy.Maximum,QSizePolicy.Fixed)
        return label

    def _row_action(self,item,receive=False):
        self.table.setCurrentItem(item)
        if receive:self.open_receipt()
        else:self.open_detail()

    def refresh_purchases(self,*args):
        self._filter_labels()
        self.monthly_summary.setVisible(self.preferences.show_monthly_purchases())
        today=date.today()
        self.monthly_heading.setText('COMPRAS · '+MONTHS[today.month-1].upper()+' '+str(today.year))
        try:
            all_purchases=self.purchases.list_purchases(PurchasesFilter(cancelled=False))
            self.capital_amount.setText(format_cop(sum(row['total_cents'] for row in all_purchases)))
            self.monthly_amount.setText(format_cop(sum(row['total_cents'] for row in all_purchases if date.fromisoformat(row['purchased_on']).replace(day=1)==today.replace(day=1))))
            provisional=sum(not row['costs_complete'] for row in all_purchases)
            self.capital_hint.setText(f'{len(all_purchases)} pedidos vigentes, sin aplicar filtros. '+
                (f'Incluye costos provisionales: {provisional} pedidos con costos por completar. ' if provisional else '')+
                '\nNo representa saldo disponible ni confirma pagos.')
            month=self.month.currentData()
            if self.use_dates.isChecked():
                start,end=self.start.date().toPython(),self.end.date().toPython()
            elif month==-1:
                start=end=None
            else:
                year=self.year.currentData()
                start=date(year,month or 1,1)
                end=date(year,month or 12,monthrange(year,month)[1] if month else 31)
            self.rows=self.purchases.list_purchases(PurchasesFilter(start,end,self.search.text(),self.state.currentData(),self.validity.currentData(),self.progress_filter.currentData(),self.received_filter.currentData()))
            shortcut_rows=self.purchases.list_purchases(PurchasesFilter(start,end,self.search.text(),cancelled=False))
            pending=sum(purchase_progress(draft_from_record(row))['state']=='costs_pending' for row in shortcut_rows)
            receiving=sum(not row['receipt'] for row in shortcut_rows)
            self.pending_count.setText(f'{pending} pedidos con costos pendientes')
            self.receipt_count.setText(f'{receiving} pendientes de recepción')
            collapsed={self.table.topLevelItem(i).data(0,Qt.UserRole) for i in range(self.table.topLevelItemCount()) if not self.table.topLevelItem(i).isExpanded()}
            self.table.clear()
            labels={'costs_pending':'Costos pendientes','allocation_pending':'Falta distribuir gastos','complete':'Costos completos','cancelled':'Anulada'}
            self.row_receive_buttons={}
            for row in self.rows:
                draft=draft_from_record(row);progress=purchase_progress(draft,bool(row['cancelled_at']))
                state=progress['state'];details=', '.join(categories_for(draft)[key] for key in progress['pending_categories'])
                if state=='costs_pending' and progress['legacy']:details='Revisar conceptos pendientes'
                purchased=date.fromisoformat(row['purchased_on'])
                supplier_name=row['supplier']+(' · '+row['supplier_alias'] if row.get('supplier_alias') else '')
                heading=supplier_name+'\n'+MONTHS[purchased.month-1]+' '+str(purchased.year)+' · Compra: '+purchased.strftime('%d/%m/%Y')
                if details:heading+='\n'+details
                parent=QTreeWidgetItem([heading,str(row['quantity'])+(' unidad' if row['quantity']==1 else ' unidades'),'','','',format_cop(row['total_cents']),''])
                parent.setData(0,Qt.UserRole,row['id']);parent.setToolTip(0,heading+'\nReferencia: '+(row['reference'] or '—'))
                for col in range(7):parent.setBackground(col,QColor('#f6f8fc'));parent.setForeground(col,QColor('#162e50'))
                font=parent.font(5);font.setBold(True);parent.setFont(5,font);parent.setTextAlignment(5,Qt.AlignRight|Qt.AlignVCenter)
                self.table.addTopLevelItem(parent);parent.setExpanded(row['id'] not in collapsed)
                parent.setForeground(0,QColor(Qt.transparent))
                heading_widget=QWidget();heading_box=QVBoxLayout(heading_widget);heading_box.setContentsMargins(4,10,4,10);heading_box.setSpacing(3);heading_box.setAlignment(Qt.AlignVCenter)
                supplier=note(escape(supplier_name),'fieldHeading');supplier.setTextFormat(Qt.RichText);supplier.setText('<b>'+escape(supplier_name)+'</b>');heading_box.addWidget(supplier)
                heading_box.addWidget(note(MONTHS[purchased.month-1]+' '+str(purchased.year)+' · Compra: '+purchased.strftime('%d/%m/%Y')))
                if details:
                    warning=note(details);warning.setStyleSheet('color: #925400; font-weight: 600;');heading_box.addWidget(warning)
                heading_widget.setToolTip(parent.toolTip(0));self.table.setItemWidget(parent,0,heading_widget)
                statuses=QWidget();status_box=QVBoxLayout(statuses);status_box.setContentsMargins(6,8,6,8);status_box.setSpacing(5);status_box.setAlignment(Qt.AlignVCenter)
                bg,fg=('#edf0f5','#68758c') if state=='cancelled' else ('#def5e7','#137844') if state=='complete' else ('#fff1d1','#925400')
                badge=self._badge(labels[state],bg,fg);badge.setToolTip(details or labels[state]);status_box.addWidget(badge)
                if not row['cancelled_at']:
                    badge=self._badge('Recibido' if row['receipt'] else 'Pendiente de recepción','#def5e7' if row['receipt'] else '#e3eaff','#137844' if row['receipt'] else '#284bb5')
                    if row['receipt']:badge.setToolTip('Recibido el '+row['receipt']['received_on'])
                    status_box.addWidget(badge)
                self.table.setItemWidget(parent,4,statuses)
                actions=QWidget();buttons=QHBoxLayout(actions);buttons.setContentsMargins(4,8,4,8);buttons.setSpacing(4)
                edit=QPushButton('Ver / editar');edit.clicked.connect(lambda checked=False,item=parent:self._row_action(item));buttons.addWidget(edit)
                if not row['cancelled_at'] and not row['receipt']:
                    receive=QPushButton('Recibir');receive.setObjectName('primary');receive.clicked.connect(lambda checked=False,item=parent:self._row_action(item,True));buttons.addWidget(receive)
                    self.row_receive_buttons[row['id']]=receive
                buttons.addWidget(attachment_button(self.purchases.connection,'purchase',row['id'],actions))
                self.table.setItemWidget(parent,6,actions)
                parent.setSizeHint(4,QSize(210,max(90,statuses.sizeHint().height())))
                for record,line in zip(row['lines'],draft.lines):
                    values=line_unit_costs(line);prefix='≈ ' if values['approximate'] else ''
                    amounts=[prefix+format_cop(int(values[key].quantize(Decimal('1'),rounding=ROUND_HALF_UP))) for key in ('purchase_cents','landed_cents')]
                    child=QTreeWidgetItem([record['code']+' · '+record['name'],str(record['quantity']),*amounts,'','',''])
                    child.setData(0,Qt.UserRole,row['id']);child.setToolTip(0,child.text(0));child.setToolTip(3,'Costo por unidad; ≈ indica redondeo. El total del pedido conserva los centavos exactos.')
                    for col in (2,3):child.setTextAlignment(col,Qt.AlignRight|Qt.AlignVCenter)
                    parent.addChild(child)
                    if state not in ('complete','cancelled'):
                        child.setToolTip(4,'Provisional')
                        cell=QWidget();box=QHBoxLayout(cell);box.setContentsMargins(6,4,6,4);box.addWidget(self._badge('Provisional','#edf0f5','#68758c'));box.addStretch();self.table.setItemWidget(child,4,cell)
            total=sum(row['total_cents'] for row in self.rows if not row['cancelled_at'])
            self.count.setText(f'{len(self.rows)} compras · Total vigente filtrado: {format_cop(total)} · Puede incluir costos provisionales.')
            self.error.clear()
        except StorageError as error:
            self.monthly_amount.setText('No disponible')
            self.capital_amount.setText('No disponible');self.capital_hint.clear()
            self.rows=[];self.table.clear();self.pending_count.setText('Costos pendientes: —');self.receipt_count.setText('Recepción: —');self.count.setText('No disponible');self.error.setText(str(error))

    def open_receipt(self):
        if self.dialog and self.dialog.isVisible():self.dialog.raise_();return
        item=self.table.currentItem()
        if item is None:return
        try:
            self.dialog=PurchaseReceiptDialog(self.purchases,self.receipts,item.data(0,Qt.UserRole),self.window())
            self.dialog.saved.connect(self.changed);self.dialog.show()
        except StorageError as error:self.error.setText(str(error))

    def changed(self,*args):
        self.refresh_purchases(); self.purchases_changed.emit()

    def _open(self,purchase_id=None):
        if self.dialog and self.dialog.isVisible(): self.dialog.raise_(); return
        try:
            self.dialog=PurchaseDialog(self.catalog,self.purchases,self.window(),purchase_id)
            self.dialog.saved.connect(self.changed); self.dialog.show()
        except StorageError as error:
            self.error.setText(str(error)); self.opening_failed.emit(str(error))

    def open_new_purchase(self): self._open()

    def open_detail(self,*args):
        item=self.table.currentItem()
        if item is not None: self._open(item.data(0,Qt.UserRole))
