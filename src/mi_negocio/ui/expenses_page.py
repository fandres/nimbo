"""Gastos integrados: resumen visual, movimientos y préstamos."""
from .attachments_dialog import attachment_button, with_attachment
from dataclasses import replace
from decimal import Decimal,ROUND_HALF_UP
from PySide6.QtCore import Signal,Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QPushButton,QLineEdit,QComboBox,QTabWidget,QHeaderView,QTableWidgetItem,QProgressBar,QSizePolicy
from ..expenses import ExpenseFilter,comparison_period
from ..storage import StorageError
from ..catalog import ValidationError
from ..loans_repository import LoansRepository
from .sales_widgets import note,error_text
from .style import format_cop
from .expense_dialog import ExpenseDialog
from .expense_filters import ExpensePeriod
from .expense_charts import ComparisonChart
from .loans_page import LoansPage,table
from .filter_popup import FilterPopup


def card(title):
    frame=QFrame();frame.setObjectName('saleSection');box=QVBoxLayout(frame);box.setContentsMargins(16,12,16,12);box.setSpacing(8)
    box.addWidget(note(title,'cardTitle'));return frame,box


def change_text(current,previous):
    if not previous:return 'Sin base de comparación' if current else 'Sin gastos en ambos períodos'
    value=(Decimal(current-previous)*100/Decimal(previous)).quantize(Decimal('.1'),rounding=ROUND_HALF_UP)
    return f'{value:+f} %'.replace('.',',')


class ExpensesPage(QWidget):
    changed=Signal()
    open_sale=Signal(int)
    opening_failed=Signal(str)
    def __init__(self,repository,settings,parent=None):
        super().__init__(parent);self.repository=repository;self.settings=settings;self.dialog=None;self.rows=[];self.summary_data={};self.filtered_summary={}
        root=QVBoxLayout(self);root.setContentsMargins(24,18,24,14);root.setSpacing(10)
        header=QHBoxLayout();header.addWidget(note('Gastos','heading'));header.addWidget(note('Controla en qué se va tu dinero.'),1)
        self.new_button=QPushButton('+ Nuevo gasto');self.new_button.setObjectName('primary');self.new_button.clicked.connect(self.open_new_expense);header.addWidget(self.new_button);root.addLayout(header)
        self.tabs=QTabWidget();self.tabs.setObjectName('expensesTabs');root.addWidget(self.tabs,1)
        self.summary_page=QWidget();self.movements_page=QWidget();self.loans=LoansPage(LoansRepository(repository.connection),settings)
        self.tabs.addTab(self.summary_page,'Resumen');self.tabs.addTab(self.movements_page,'Movimientos');self.tabs.addTab(self.loans,'Préstamos')
        # A shared filter row above the tab contents keeps period/account in sync.
        self.filters=QWidget();bar=QHBoxLayout(self.filters);bar.setContentsMargins(0,0,0,0)
        self.search=QLineEdit();self.search.setClearButtonEnabled(True);self.search.setPlaceholderText('Buscar concepto o plataforma');self.category=QComboBox();self.state=QComboBox()
        self.state.addItem('Todos los estados',None);self.state.addItem('Pagados / a tarjeta',True);self.state.addItem('Pendientes',False)
        self.account=QComboBox();self.period=ExpensePeriod(self);self.more=QPushButton('Más filtros')
        for w in (self.search,self.category,self.state,self.account,self.period,self.more):bar.addWidget(w,1 if w is self.search else 0)
        bar.addStretch()
        self.more_popup=FilterPopup('Movimientos incluidos',self);self.validity=QComboBox()
        self.validity.addItem('Vigentes',False);self.validity.addItem('Anulados',True);self.validity.addItem('Todos',None)
        self.platform=QComboBox();self.platform.setAccessibleName('Comisiones de plataforma');self.date_basis=QComboBox();self.date_basis.addItem('Fecha del gasto','spent');self.date_basis.addItem('Fecha de pago','paid')
        self.more_popup.box.addWidget(note('Comisiones de plataforma'));self.more_popup.box.addWidget(self.platform);self.more_popup.box.addWidget(note('Aplicar período a'));self.more_popup.box.addWidget(self.date_basis)
        self.more_popup.box.addWidget(self.validity);self.more_popup.box.addWidget(note('Los anulados se conservan para consulta; nunca se suman a los totales.'));self.more_popup.finish();self.more.clicked.connect(lambda:self.more_popup.open_below(self.more))
        summary=QVBoxLayout(self.summary_page);summary.setContentsMargins(0,10,0,0);summary.setSpacing(10)
        self.summary_notice=note('Gastos registrados, incluidos los pendientes. No equivale a dinero pagado.');summary.addWidget(self.summary_notice)
        charts=QHBoxLayout();charts.setSpacing(12)
        category_card,category_box=card('Gastos por categoría');self.category_chart=table(['Categoría','Distribución','Valor · COP','%'])
        self.category_chart.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);self.category_chart.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for col,width in [(2,150),(3,66)]:self.category_chart.horizontalHeader().setSectionResizeMode(col,QHeaderView.Fixed);self.category_chart.setColumnWidth(col,width)
        self.category_chart.verticalHeader().setDefaultSectionSize(40);self.category_chart.setMinimumHeight(160);category_box.addWidget(self.category_chart,1)
        self.category_empty=note('Aún no hay gastos para este período.');category_box.addWidget(self.category_empty);charts.addWidget(category_card,5)
        comparison_card,comparison_box=card('Comparación con período equivalente');self.comparison=note('','sectionValue');self.comparison_dates=note('');comparison_box.addWidget(self.comparison);comparison_box.addWidget(self.comparison_dates)
        self.comparison_chart=ComparisonChart();comparison_box.addWidget(self.comparison_chart,1)
        self.capital_note=note('');comparison_box.addWidget(self.capital_note);charts.addWidget(comparison_card,4);summary.addLayout(charts,1)
        recent_card,recent_box=card('Últimos cuatro gastos');self.recent=table(['Fecha','Concepto','Categoría','Estado','Valor · COP']);self.recent.setMinimumHeight(210)
        self.recent.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for col,width in [(0,100),(2,195),(3,100),(4,150)]:self.recent.horizontalHeader().setSectionResizeMode(col,QHeaderView.Fixed);self.recent.setColumnWidth(col,width)
        self.recent.verticalHeader().setDefaultSectionSize(38);recent_box.addWidget(self.recent)
        all_button=QPushButton('Ver todos en Movimientos →');all_button.setObjectName('quietAction');all_button.clicked.connect(self.show_all_movements);recent_box.addWidget(all_button);summary.addWidget(recent_card)
        self.recent.cellDoubleClicked.connect(self.open_recent)
        movements=QVBoxLayout(self.movements_page);movements.setContentsMargins(0,10,0,0);metrics=QHBoxLayout();self.metrics=[]
        for title,color in [('GASTOS DEL PERÍODO','#183052'),('PAGADO / CARGADO A TARJETA','#137844'),('PENDIENTE POR PAGAR','#975d00'),('VS PERÍODO EQUIVALENTE','#64748b')]:
            frame=QFrame();frame.setObjectName('saleSection');box=QVBoxLayout(frame);box.addWidget(note(title));value=note('—','sectionValue');value.setStyleSheet('color:'+color);box.addWidget(value);metrics.addWidget(frame);self.metrics.append(value)
        movements.addLayout(metrics)
        self.table=table(['Fecha','Concepto','Categoría','Cuenta','Estado','Valor · COP','Acciones'])
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for col,width in [(0,100),(2,160),(3,115),(4,95),(5,150),(6,155)]:self.table.horizontalHeader().setSectionResizeMode(col,QHeaderView.Fixed);self.table.setColumnWidth(col,width)
        self.table.verticalHeader().setDefaultSectionSize(76);movements.addWidget(self.table,1);self.count=note('');movements.addWidget(self.count)
        self.table.cellDoubleClicked.connect(self.open_selected)
        self.error=note('','error');root.addWidget(self.error)
        self.tabs.currentChanged.connect(self._tab_changed)
        for signal in (self.search.textChanged,self.category.currentIndexChanged,self.state.currentIndexChanged,self.account.currentIndexChanged,self.period.changed,self.validity.currentIndexChanged,self.platform.currentIndexChanged,self.date_basis.currentIndexChanged):signal.connect(self.refresh)
        self.loans.changed.connect(self._saved)
        self.refresh_options();self.refresh();self._tab_changed(0)

    def refresh_options(self):
        try:
            for combo in (self.account,self.category,self.platform):combo.blockSignals(True)
            account,category=self.account.currentData(),self.category.currentData();self.account.clear();self.category.clear()
            platform=self.platform.currentData();self.platform.clear();self.platform.addItem('Todas las plataformas y gastos',None)
            for key,name in self.repository.commission_methods():self.platform.addItem(name,key)
            self.platform.setCurrentIndex(max(0,self.platform.findData(platform)))
            self.account.addItem('Todas las cuentas',None);self.category.addItem('Todas las categorías',None)
            for a in self.settings.list_accounts(True,include_cards=True):self.account.addItem(a.name,a.id)
            for c in self.repository.categories(True):self.category.addItem(c['name'],'manual:'+str(c['id']))
            for key,name in [('commission','Comisión de venta'),('shipping','Envío de venta'),('loan_interest','Intereses de préstamos'),('card_interest_cents','Intereses de tarjeta'),('card_fee_cents','Cargos de tarjeta')]:self.category.addItem(name,key)
            self.account.setCurrentIndex(max(0,self.account.findData(account)));self.category.setCurrentIndex(max(0,self.category.findData(category)))
        except StorageError as e:self.error.setText(str(e))
        finally:
            for combo in (self.account,self.category,self.platform):combo.blockSignals(False)

    def _tab_changed(self,index):
        for page in (self.summary_page,self.movements_page):page.layout().removeWidget(self.filters)
        if index!=2:self.tabs.widget(index).layout().insertWidget(0,self.filters)
        for w in (self.search,self.category,self.state):w.setVisible(index==1)
        self.more.setVisible(index!=2)
        self.filters.setVisible(index!=2)
        self.more_popup.hide();self.period.popup.hide()
        if index==2:self.loans.refresh()

    def refresh(self,*args):
        try:
            start,end,monthly=self.period.period();before_start,before_end=comparison_period(start,end,monthly)
            basic=ExpenseFilter(start,end,self.account.currentData(),method_id=self.platform.currentData(),date_basis=self.date_basis.currentData())
            self.more.setText('Más filtros'+(' · '+str(int(basic.method_id is not None)+int(basic.date_basis=='paid')) if basic.method_id is not None or basic.date_basis=='paid' else ''))
            self.more.setToolTip('Plataforma: '+self.platform.currentText()+' · '+self.date_basis.currentText())
            summary=self.repository.summary(basic);before=self.repository.summary(replace(basic,start=before_start,end=before_end))
            self.summary_data=summary;self.previous_summary=before
            detail=replace(basic,category_key=self.category.currentData(),paid=self.state.currentData(),query=self.search.text(),cancelled=self.validity.currentData())
            self.rows=self.repository.list_movements(detail);filtered=self.repository.summary(detail);self.filtered_summary=filtered
            old_filtered=self.repository.summary(replace(detail,start=before_start,end=before_end))
            self.metrics[0].setText(format_cop(filtered['total_cents']));self.metrics[1].setText(format_cop(filtered['paid_cents']));self.metrics[2].setText(format_cop(filtered['pending_cents']))
            self.metrics[3].setText(change_text(filtered['total_cents'],old_filtered['total_cents']))
            self.metrics[3].setToolTip(f'Antes: {format_cop(old_filtered["total_cents"])} · {before_start:%d/%m/%Y} – {before_end:%d/%m/%Y}. Mismos filtros.')
            self._render_categories(summary,before)
            self.comparison.setText(change_text(summary['total_cents'],before['total_cents']))
            difference=summary['total_cents']-before['total_cents']
            self.comparison_dates.setText(f"Actual: {start:%d/%m/%Y} – {end:%d/%m/%Y}\nAnterior: {before_start:%d/%m/%Y} – {before_end:%d/%m/%Y}\n{format_cop(abs(difference))} {'más' if difference>=0 else 'menos'} en gastos registrados.")
            self.comparison_chart.set_values(before['total_cents'],summary['total_cents'],(f'{before_start:%d/%m} – {before_end:%d/%m}',f'{start:%d/%m} – {end:%d/%m}'))
            self.capital_note.setVisible(basic.method_id is None)
            self.capital_note.setText('Capital de préstamos pagado: '+format_cop(summary['loan_capital_cents'])+' · Fuera de gastos.')
            self.summary_notice.setText(('Gastos pagados en el período, según fecha de pago.' if basic.date_basis=='paid' else 'Gastos registrados, incluidos los pendientes. No equivale a dinero pagado.')+(' Incluye comisiones estimadas.' if summary['estimated'] else ''))
            self.recent_rows=summary['recent'];self.recent.setRowCount(len(self.recent_rows))
            for i,r in enumerate(self.recent_rows):
                values=[r['paid_on'] if self.date_basis.currentData()=='paid' else r['spent_on'],r['concept'],r['category'],'Cargado a tarjeta' if r['origin']=='card' else 'Pagado' if r['paid'] else 'Pendiente',format_cop(r['amount_cents'])]
                for j,value in enumerate(values):self.recent.setItem(i,j,QTableWidgetItem(value))
                self.recent.item(i,4).setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            for widget in (self.table,self.recent):widget.horizontalHeaderItem(0).setText('Pago' if basic.date_basis=='paid' else 'Fecha')
            self._render_movements();self.error.clear()
        except (StorageError,ValidationError,ValueError) as e:
            self.error.setText(error_text(e));self.rows=[];self.recent_rows=[];self.summary_data={};self.filtered_summary={};self.table.setRowCount(0);self.recent.setRowCount(0);self.category_chart.setRowCount(0)
            for value in self.metrics:value.setText('—')
            self.comparison.setText('No disponible');self.comparison_dates.clear();self.comparison_chart.set_values(0,0,('Anterior','Actual'));self.capital_note.clear();self.count.setText('No disponible')

    def _render_categories(self,summary,previous):
        for i in range(self.category_chart.rowCount()):
            widget=self.category_chart.cellWidget(i,1)
            if widget:widget.hide()
        self.category_chart.setRowCount(0)
        rows=summary['categories'];self.category_chart.setRowCount(len(rows));self.category_empty.setVisible(not rows)
        old={r['key']:r['amount_cents'] for r in previous['categories']}
        total=summary['total_cents']
        for i,row in enumerate(rows):
            share=Decimal(row['amount_cents'])*100/Decimal(total) if total else Decimal(0)
            name=QTableWidgetItem(row['name']);name.setToolTip('Variación por categoría: '+change_text(row['amount_cents'],old.get(row['key'],0)));self.category_chart.setItem(i,0,name)
            bar=QProgressBar();bar.setRange(0,1000);bar.setValue(round(share*10));bar.setTextVisible(False);bar.setStyleSheet('QProgressBar {background:#edf1f8;border:none;border-radius:5px;max-height:12px;} QProgressBar::chunk {background:#315fda;border-radius:5px;}');bar.setAccessibleName(row['name']+f': {share:.1f} %');self.category_chart.setCellWidget(i,1,bar)
            amount=QTableWidgetItem(format_cop(row['amount_cents']));amount.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter);self.category_chart.setItem(i,2,amount);self.category_chart.setItem(i,3,QTableWidgetItem(f'{share:.0f}%'))

    def _render_movements(self):
        for i in range(self.table.rowCount()):
            widget=self.table.cellWidget(i,6)
            if widget:widget.hide()
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            detail=row['detail'] or ('Pago estimado: '+row['due_on'] if row['due_on'] and not row['paid'] else '')
            values=[row['paid_on'] if self.date_basis.currentData()=='paid' else row['spent_on'],row['concept']+('\n'+detail if detail else ''),row['category'],row['account'],'Anulado' if row['cancelled'] else 'Cargado a tarjeta' if row['origin']=='card' else 'Pagado' if row['paid'] else 'Pendiente',format_cop(row['amount_cents'])]
            for j,value in enumerate(values):
                item=QTableWidgetItem(value);item.setToolTip(value)
                if row['cancelled']:
                    item.setForeground(QColor('#8995aa'));font=item.font();font.setStrikeOut(True);item.setFont(font)
                self.table.setItem(i,j,item)
            self.table.item(i,5).setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.table.item(i,4).setForeground(QColor('#8995aa' if row['cancelled'] else '#137844' if row['paid'] else '#975d00'))
            label='Ver tarjeta' if row['origin']=='card' else 'Ver venta' if row['origin']=='sale' else 'Ver préstamo' if row['origin']=='loan' else 'Ver historial' if row['cancelled'] else 'Editar' if row['paid'] else 'Marcar pagado'
            button=QPushButton(label)
            if row['origin']=='manual' and not row['paid'] and not row['cancelled']:button.setObjectName('primary')
            button.clicked.connect(lambda checked=False,r=row:self.open_row(r,mark_paid=r['origin']=='manual' and not r['paid'] and not r['cancelled']))
            kind={'manual':'expense','sale':'sale','loan':'loan_payment','card':'card_charge'}[row['origin']]
            key=row['order_id'] if row['origin'] in ('loan','card') else row['source_id']
            self.table.setCellWidget(i,6,with_attachment(button,self.repository.connection,kind,key))
        self.count.setText(('Comisiones: '+self.platform.currentText()+' · ' if self.platform.currentData() is not None else '')+self.date_basis.currentText()+' · '+f"{self.filtered_summary['count']} gastos vigentes · {sum(r['cancelled'] for r in self.rows)} anulados (no suman al total). Doble clic para ver o editar.")

    def show_all_movements(self):
        self.search.clear();self.category.setCurrentIndex(0);self.state.setCurrentIndex(0);self.validity.setCurrentIndex(0);self.tabs.setCurrentIndex(1);self.refresh()

    def open_recent(self,row,*args):
        if 0<=row<len(self.recent_rows):self.open_row(self.recent_rows[row])
    def open_selected(self,row,*args):
        if 0<=row<len(self.rows):self.open_row(self.rows[row])
    def open_row(self,row,mark_paid=False):
        if row['origin']=='sale':self.open_sale.emit(row['source_id']);return
        if row['origin']=='loan':self.tabs.setCurrentIndex(2);self.loans.select_loan(row['source_id']);return
        if row['origin']=='card':
            from ..credit_cards import CreditCardsRepository
            from .credit_card_dialogs import CardDetailDialog
            self.card_dialog=CardDetailDialog(CreditCardsRepository(self.repository.connection),row['source_id'],self);self.card_dialog.changed.connect(self._saved);self.card_dialog.show();return
        self._open_dialog(row['source_id'],mark_paid)
    def open_new_expense(self):self._open_dialog()
    def _open_dialog(self,key=None,mark_paid=False):
        if self.dialog and self.dialog.isVisible():self.dialog.raise_();return
        try:
            self.dialog=ExpenseDialog(self.repository,self.settings,self.window(),key,mark_paid);self.dialog.saved.connect(self._saved);self.dialog.finished.connect(lambda *args:self._saved());self.dialog.show()
        except StorageError as e:self.error.setText(str(e));self.opening_failed.emit(str(e))
    def _saved(self):self.refresh_options();self.refresh();self.changed.emit()
