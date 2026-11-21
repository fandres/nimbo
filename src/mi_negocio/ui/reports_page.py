"""Independent read-only report filters, preview and atomic PDF export."""
from calendar import monthrange
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QSignalBlocker, Signal, Qt
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QComboBox, QLineEdit, QPushButton, QTextBrowser, QFileDialog,
    QMessageBox, QFrame, QButtonGroup, QSizePolicy)

from ..retention_certificates import RetentionCertificatesRepository, STATUSES
from .retentions_report import build_retentions_report
from ..storage import StorageError
from ..catalog import ValidationError
from ..purchases import PurchasesFilter
from ..purchases_repository import PurchasesRepository
from .purchases_report import build_purchases_report
from ..sales import SalesFilter
from ..expenses import ExpenseFilter
from ..settings_repository import SettingsRepository
from ..sales_repository import SalesRepository
from ..expenses_repository import ExpensesRepository
from ..money_repository import MoneyRepository
from ..profitability_repository import ProfitabilityRepository
from .sales_widgets import date_edit, note
from .expense_filters import MONTHS
from .sales_report import build_sales_report
from .expenses_report import build_expenses_report
from .profitability_report import build_profitability_report
from .money_report import build_money_report, write_money_pdf

TITLES = {'sales': 'Ventas', 'expenses': 'Gastos', 'money': 'Dinero', 'profitability': 'Rentabilidad', 'purchases': 'Compras', 'retentions': 'Retenciones'}


class ReportPreview(QTextBrowser):
    def loadResource(self, resource_type, url):
        # Reports contain only escaped text and internal styling, never attachments.
        return None


def combo(items):
    widget = QComboBox()
    for label, value in items:
        widget.addItem(label, value)
    return widget


def refill(widget, items):
    value = widget.currentData()
    with QSignalBlocker(widget):
        widget.clear()
        for label, key in items:
            widget.addItem(label, key)
        widget.setCurrentIndex(max(0, widget.findData(value)))


class ReportPanel(QWidget):
    preview_changed = Signal()

    def __init__(self, kind, connection, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.settings = SettingsRepository(connection)
        self.sales = SalesRepository(connection)
        self.purchases = PurchasesRepository(connection)
        self.certificates = RetentionCertificatesRepository(connection)
        self.expenses = ExpensesRepository(connection)
        self.money = MoneyRepository(connection)
        self.profitability = ProfitabilityRepository(connection)
        self.html = ''
        self.rows = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        filters = QFrame()
        filters.setObjectName('reportFilters')
        filters.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
        grid = QGridLayout(filters)
        grid.setContentsMargins(0, 0, 0, 8)
        grid.setSpacing(10)
        today = date.today()
        self.month = combo([(name, i) for i, name in enumerate(MONTHS, 1)] + [('Personalizado', None)])
        self.month.setCurrentIndex(today.month-1)
        self.year = combo([(str(y), y) for y in range(today.year, today.year-6, -1)] + [('Más años…', None)])
        self.selected_year = today.year
        self.start, self.end = date_edit(), date_edit()
        self.start.setDate(QDate(today.year, today.month, 1))
        self.end.setDate(QDate.currentDate())
        if kind=='retentions':
            self.month.insertItem(0,'Todo el año',0)
            self.month.setCurrentIndex(0)
            self.start.setDate(QDate(today.year,1,1))
        # Month/year selectors remain internal adapters for the existing date logic.
        self.month.setParent(self);self.month.hide()
        self.year.setParent(self);self.year.hide()
        self.period_buttons = {}
        self.period_group = QButtonGroup(self)
        self.period_bar = QWidget()
        periods = QHBoxLayout(self.period_bar);periods.setContentsMargins(0,0,0,0)
        for key,label in [('month','Este mes'),('previous','Mes pasado'),('year','Este año'),('custom','Personalizado')]:
            button=QPushButton(label);button.setObjectName('reportPeriod');button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            self.period_group.addButton(button);self.period_buttons[key]=button
            button.clicked.connect(lambda _=False,k=key:self.apply_period(k));periods.addWidget(button)
        self.period_buttons['year' if kind=='retentions' else 'month'].setChecked(True)
        self.dates_bar=QWidget()
        dates=QHBoxLayout(self.dates_bar);dates.setContentsMargins(0,0,0,0)
        for label,field in [('Desde',self.start),('Hasta',self.end)]:
            field.setAccessibleName(label);field.setMinimumWidth(125)
            dates.addWidget(note(label));dates.addWidget(field)
        dates.addStretch()
        grid.addWidget(self.period_bar,0,0)
        grid.addWidget(self.dates_bar,0,1)
        grid.setColumnStretch(1,1)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('Buscar cliente, producto o factura…' if kind in ('sales', 'profitability') else 'Buscar concepto o plataforma…' if kind=='expenses' else 'Buscar proveedor, alias, producto o factura…' if kind=='purchases' else 'Buscar concepto o cuenta…')
        if kind=='retentions':self.search.setPlaceholderText('Buscar cliente, cédula / NIT, correo o factura…')
        self.search.setAccessibleName('Búsqueda del informe')
        self.account = combo([('Todas las cuentas', None)])
        self.account.setAccessibleName('Cuenta')
        self.state = combo([('Todos los estados', None), ('Recibido' if kind=='sales' else 'Pagado / a tarjeta', True), ('Pendiente', False)])
        self.validity = combo([('Vigentes', False), ('Anulados', True), ('Todos', None)])
        self.withholding = combo([('Todas las retenciones', None), ('Con retención', True), ('Sin retención', False)])
        self.category = combo([('Todas las categorías', None)])
        self.platform = combo([('Todas las plataformas y gastos', None)])
        self.date_basis = combo([('Fecha del gasto', 'spent'), ('Fecha de pago', 'paid')])
        self.certificate_status=combo([('Todos los certificados',None)]+[(label,key) for key,label in STATUSES.items()])
        extras = []
        if kind=='sales':
            extras = [('Estado de cobro', self.state), ('Vigencia', self.validity), ('Retención', self.withholding)]
        elif kind=='retentions':
            extras=[('Certificado anual',self.certificate_status)]
        elif kind=='purchases':
            extras = [('Vigencia',self.validity)]
        elif kind=='expenses':
            extras = [('Estado', self.state), ('Vigencia', self.validity), ('Categoría', self.category), ('Comisiones de plataforma', self.platform)]
        self.filter_fields=[self.search]
        if kind not in ('profitability','purchases','retentions'):
            self.filter_fields.append(self.account)
        for label,field in extras:
            field.setAccessibleName(label);self.filter_fields.append(field)
        if kind=='expenses':
            self.date_basis.setAccessibleName('Aplicar período a');self.filter_fields.append(self.date_basis)
        if kind=='sales':self.state.setItemText(0,'Todos los cobros')
        self.clear_button=QPushButton('Limpiar filtros');self.clear_button.setObjectName('reportLink')
        self.clear_button.clicked.connect(self.clear_filters)
        self.filter_fields.append(self.clear_button)
        self.filter_grid=QGridLayout();self.filter_grid.setSpacing(8)
        self.filter_columns=None
        grid.addLayout(self.filter_grid,2,0,1,2)
        self.filters_grid=grid
        self.arrange_filters(1100)
        root.addWidget(filters)
        self.preview_frame=QFrame();self.preview_frame.setObjectName('reportPreviewFrame')
        preview_layout=QVBoxLayout(self.preview_frame);preview_layout.setContentsMargins(14,12,14,14)
        actions = QHBoxLayout()
        actions.addWidget(note('Vista previa del PDF','cardTitle'))
        self.preview_hint=note('Solo lectura · se actualiza con los filtros')
        self.preview_hint.setWordWrap(False)
        actions.addWidget(self.preview_hint)
        actions.addStretch(1)
        self.update_button = QPushButton('Actualizar')
        self.update_button.setObjectName('reportLink')
        self.update_button.setToolTip('Volver a consultar los datos y las opciones de los filtros')
        self.export_button = QPushButton('Exportar PDF',self)
        self.export_button.hide()
        if kind=='retentions':
            self.certificates_button=QPushButton('Gestionar certificados')
            self.certificates_button.clicked.connect(self.manage_certificates)
            actions.addWidget(self.certificates_button)
        actions.addWidget(self.update_button)
        preview_layout.addLayout(actions)
        self.error = note('', 'error')
        self.error.hide()
        self.status = note('')
        self.status.hide()
        root.addWidget(self.error)
        root.addWidget(self.status)
        self.preview = ReportPreview()
        self.preview.setOpenLinks(False)
        self.preview.setOpenExternalLinks(False)
        self.preview.setStyleSheet('QTextBrowser {background: white; border: 1px solid #e0e6f0; border-radius: 12px; padding: 0px;}')
        self.preview.document().setDocumentMargin(22)
        option=self.preview.document().defaultTextOption()
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.preview.document().setDefaultTextOption(option)
        preview_layout.addWidget(self.preview, 1)
        root.addWidget(self.preview_frame,1)
        self.month.currentIndexChanged.connect(self.select_month)
        self.year.currentIndexChanged.connect(self.select_year)
        self.start.dateChanged.connect(self.custom_dates)
        self.end.dateChanged.connect(self.custom_dates)
        self.search.textChanged.connect(self.refresh)
        for widget in [self.account] + [field for _, field in extras] + ([self.date_basis] if kind=='expenses' else []):
            widget.currentIndexChanged.connect(self.refresh)
            widget.currentTextChanged.connect(widget.setToolTip)
        self.update_button.clicked.connect(self.refresh_options)
        self.export_button.clicked.connect(self.export_pdf)
        self.refresh_options()

    def arrange_filters(self,width):
        columns=7 if width>=1280 else 4 if width>=900 else 3
        layout_key=(columns,width>=960)
        if layout_key==self.filter_columns:return
        self.filter_columns=layout_key
        while self.filter_grid.count():self.filter_grid.takeAt(0)
        for col in range(8):self.filter_grid.setColumnStretch(col,0)
        if self.kind=='sales':
            # Reserve only the space needed by each selector; search takes the rest.
            for col,field in enumerate(self.filter_fields):
                self.filter_grid.addWidget(field,0,col)
                if isinstance(field,QComboBox):
                    label=field.itemText(0)
                    field.setFixedWidth(field.fontMetrics().horizontalAdvance(label)+64)
                    field.setToolTip(field.currentText())
                elif field is self.clear_button:
                    field.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
            self.search.setMinimumWidth(150)
            self.filter_grid.setColumnStretch(0,1)
        else:
            self.filter_grid.addWidget(self.search,0,0,1,2)
            row,col=0,2
            for field in self.filter_fields[1:]:
                if col>=columns:row+=1;col=0
                field.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
                self.filter_grid.addWidget(field,row,col);col+=1
            for col in range(columns):self.filter_grid.setColumnStretch(col,1)
        self.filters_grid.removeWidget(self.dates_bar)
        self.filters_grid.addWidget(self.dates_bar,0 if width>=960 else 1,1 if width>=960 else 0,1,1 if width>=960 else 2)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.arrange_filters(event.size().width())
        self.preview_hint.setVisible(event.size().width()>=1000)

    def apply_period(self,key):
        if key=='custom':
            with QSignalBlocker(self.month):self.month.setCurrentIndex(self.month.findData(None))
            self.start.setFocus()
            return
        today=QDate.currentDate()
        first=QDate(today.year(),today.month(),1)
        last=today
        if key=='previous':
            first=first.addMonths(-1);last=first.addDays(first.daysInMonth()-1)
        elif key=='year':first=QDate(today.year(),1,1)
        with QSignalBlocker(self.start),QSignalBlocker(self.end),QSignalBlocker(self.month):
            self.start.setDate(first);self.end.setDate(last)
            self.month.setCurrentIndex(self.month.findData(None))
        self.period_buttons[key].setChecked(True)
        self.refresh()

    def clear_filters(self):
        fields=[self.search,self.account,self.state,self.validity,self.withholding,
                self.category,self.platform,self.date_basis,self.certificate_status]
        blockers=[QSignalBlocker(field) for field in fields]
        self.search.clear()
        for field in fields[1:]:field.setCurrentIndex(0)
        del blockers
        self.apply_period('year' if self.kind=='retentions' else 'month')

    def select_year(self):
        value = self.year.currentData()
        if value is None:
            oldest = self.year.itemData(self.year.count()-2)
            with QSignalBlocker(self.year):
                self.year.removeItem(self.year.count()-1)
                for y in range(oldest-1, max(0, oldest-6), -1):
                    self.year.addItem(str(y), y)
                if oldest>6:
                    self.year.addItem('Más años…', None)
                self.year.setCurrentIndex(self.year.findData(self.selected_year))
            self.year.showPopup()
            return
        self.selected_year = value
        self.select_month()

    def select_month(self):
        month, year = self.month.currentData(), self.year.currentData()
        if month==0 and year is not None:
            last=min(date(year,12,31),date.today())
            with QSignalBlocker(self.start), QSignalBlocker(self.end):
                self.start.setDate(QDate(year,1,1))
                self.end.setDate(QDate(last.year,last.month,last.day))
            self.refresh()
            return
        if month is not None and year is not None:
            if date(year, month, 1)>date.today():
                self.fail(ValueError('Selecciona un período que ya haya comenzado.'))
                return
            last = date(year, month, monthrange(year, month)[1])
            if (year, month)==(date.today().year, date.today().month):
                last = date.today()
            with QSignalBlocker(self.start), QSignalBlocker(self.end):
                self.start.setDate(QDate(year, month, 1))
                self.end.setDate(QDate(last.year, last.month, last.day))
        self.refresh()

    def custom_dates(self):
        self.period_buttons['custom'].setChecked(True)
        with QSignalBlocker(self.month):
            self.month.setCurrentIndex(self.month.findData(None))
        self.refresh()

    def refresh_options(self):
        try:
            accounts = [('Todas las cuentas', None)] + [(a.name, a.id) for a in self.settings.list_accounts(True, include_cards=True)]
            if self.kind=='money':
                accounts.append(('Retenciones de renta', -1))
            refill(self.account, accounts)
            if self.kind=='expenses':
                categories = [('Todas las categorías', None)] + [(c['name'], 'manual:'+str(c['id'])) for c in self.expenses.categories(True)]
                categories += [('Comisión de venta', 'commission'), ('Envío de venta', 'shipping'), ('Intereses de préstamos', 'loan_interest'), ('Intereses de tarjeta', 'card_interest_cents'), ('Cargos de tarjeta', 'card_fee_cents')]
                refill(self.category, categories)
                refill(self.platform, [('Todas las plataformas y gastos', None)] + [(name, key) for key, name in self.expenses.commission_methods()])
            self.refresh()
        except (StorageError, ValueError) as exc:
            self.fail(exc)

    def fail(self, error):
        self.html = ''
        self.rows = []
        self.preview.clear()
        self.error.setText(str(error))
        self.error.show()
        self.export_button.setEnabled(False)
        self.preview_changed.emit()

    def refresh(self, *_):
        self.status.hide()
        try:
            month, year = self.month.currentData(), self.year.currentData()
            if month and year is not None and date(year, month, 1)>date.today():
                raise ValueError('Selecciona un período que ya haya comenzado.')
            start, end = self.start.date().toPython(), self.end.date().toPython()
            if start>end:
                raise ValueError('La fecha inicial debe ser anterior o igual a la final.')
            account, query = self.account.currentData(), self.search.text().strip()
            filters = [('Período', f'{start:%d/%m/%Y} al {end:%d/%m/%Y}'), ('Cuenta', self.account.currentText()), ('Búsqueda', query or 'Sin búsqueda')]
            if self.kind=='sales':
                filters += [('Estado de cobro', self.state.currentText()), ('Vigencia', self.validity.currentText()), ('Retención', self.withholding.currentText())]
                rows = self.sales.list_sales(SalesFilter(start=start, end=end, account_id=account, received=self.state.currentData(), query=query, has_withholding=self.withholding.currentData(), cancelled=self.validity.currentData()))
                html = build_sales_report(rows, filters)
            elif self.kind=='expenses':
                filters += [('Estado', self.state.currentText()), ('Vigencia', self.validity.currentText()), ('Categoría', self.category.currentText()), ('Plataforma', self.platform.currentText()), ('Fechas aplicadas a', self.date_basis.currentText())]
                rows = self.expenses.list_movements(ExpenseFilter(start=start, end=end, account_id=account, category_key=self.category.currentData(), paid=self.state.currentData(), query=query, cancelled=self.validity.currentData(), method_id=self.platform.currentData(), date_basis=self.date_basis.currentData()))
                html = build_expenses_report(rows, filters, self.date_basis.currentData())
            elif self.kind=='retentions':
                filters=[item for item in filters if item[0]!='Cuenta']
                filters.append(('Certificado anual',self.certificate_status.currentText()))
                rows=self.certificates.list(start,end,query,self.certificate_status.currentData())
                html=build_retentions_report(rows,filters)
            elif self.kind=='purchases':
                filters=[item for item in filters if item[0]!='Cuenta']
                filters.append(('Vigencia',self.validity.currentText()))
                rows=self.purchases.list_purchases(PurchasesFilter(start=start,end=end,query=query,cancelled=self.validity.currentData()))
                html=build_purchases_report(rows,filters)
            elif self.kind=='profitability':
                snapshot = self.profitability.report(start, end, query)
                rows = snapshot['rows']
                html = build_profitability_report(snapshot, start, end)
            else:
                rows = self.money.movements(start, end, account, query)
                html = build_money_report(rows, start, end, self.account.currentText(), query, account)
            if self.kind in ('sales','expenses'):
                from .quick_entries_report import provisional_section
                extra=provisional_section(self.settings.connection,self.kind,start,end,query,account,
                    self.state.currentData(),self.validity.currentData(),
                    withholding=self.withholding.currentData() if self.kind=='sales' else None,
                    category=self.category.currentData() if self.kind=='expenses' else None,
                    platform=self.platform.currentData() if self.kind=='expenses' else None,
                    date_basis=self.date_basis.currentData() if self.kind=='expenses' else 'spent')
                html=html.replace('</body>',extra+'</body>') if '</body>' in html else html+extra
            self.rows, self.html = rows, html
            self.preview.setHtml(html)
            self.error.clear()
            self.error.hide()
            self.export_button.setEnabled(True)
            self.preview_changed.emit()
        except (StorageError, ValidationError, ValueError) as exc:
            self.fail(exc)

    def manage_certificates(self):
        from .retention_certificates_dialog import RetentionCertificatesDialog
        self.refresh()
        if not self.html:return
        dialog=RetentionCertificatesDialog(self.certificates,self.rows,self)
        dialog.finished.connect(self.refresh)
        dialog.show()
        return dialog

    def export_pdf(self):
        if not self.html:
            return
        # Export the reviewed snapshot, not a fresh query with possibly changed records.
        html = self.html
        path, _ = QFileDialog.getSaveFileName(self, 'Guardar informe', f'Nimbo-{self.kind}-{date.today()}.pdf', 'Documento PDF (*.pdf)')
        if not path:
            return
        if not path.lower().endswith('.pdf'):
            path += '.pdf'
        if Path(path).exists() and QMessageBox.question(self, 'Reemplazar informe', 'El archivo ya existe. ¿Quieres reemplazarlo?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)!=QMessageBox.Yes:
            return
        try:
            write_money_pdf(path, html, title='Nimbo · '+TITLES[self.kind])
            self.status.setText('PDF guardado en: '+path)
            self.status.show()
        except (OSError, ValueError, RuntimeError) as exc:
            self.error.setText(str(exc))
            self.error.show()


class ReportsPage(QWidget):
    def __init__(self, connection, parent=None):
        super().__init__(parent)
        self.setObjectName('reportsPage')
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        heading = QHBoxLayout()
        heading.addWidget(note('Informes', 'heading'))
        heading.addWidget(note('Consulta tus datos y exporta el informe del período.'), 1)
        self.export_button=QPushButton('Exportar PDF');self.export_button.setObjectName('primary')
        self.export_button.setMinimumWidth(150)
        self.export_button.clicked.connect(lambda:self.panels[self.tabs.currentIndex()].export_pdf())
        heading.addWidget(self.export_button)
        root.addLayout(heading)
        self.tabs = QTabWidget()
        self.panels = []
        for kind, title in TITLES.items():
            panel = ReportPanel(kind, connection)
            panel.preview_changed.connect(self.sync_export)
            self.panels.append(panel)
            self.tabs.addTab(panel, title)
        root.addWidget(self.tabs, 1)
        self.tabs.currentChanged.connect(self.refresh)
        self.sync_export()
        self.setStyleSheet(REPORT_STYLE)

    def sync_export(self):
        if self.panels:
            self.export_button.setEnabled(bool(self.panels[self.tabs.currentIndex()].html))

    def refresh(self, *_):
        self.panels[self.tabs.currentIndex()].refresh_options()


REPORT_STYLE = """
QWidget#reportsPage { background: #f5f6fb; }
QFrame#reportFilters { background: transparent; border: none; }
QFrame#reportPreviewFrame { background: #e9edf6; border-radius: 16px; }
QPushButton#reportPeriod { border-radius: 17px; padding: 8px 14px; font-weight: 500; }
QPushButton#reportPeriod:checked { background: #e4eaff; border: 1px solid #315cf5; color: #2445b8; font-weight: 600; }
QPushButton#reportPeriod:hover { background: #edf1ff; border-color: #315cf5; }
QPushButton#reportPeriod:focus { border: 2px solid #315cf5; }
QPushButton#reportLink { background: transparent; border: none; color: #3158dc; padding: 8px; }
QPushButton#reportLink:hover { background: #dce5ff; }
QPushButton#reportLink:focus { border: 1px solid #315cf5; }
QTabWidget::pane { border: none; border-top: 1px solid #e0e5ef; }
QTabBar::tab { background: transparent; border: none; padding: 12px 16px; color: #5b6c8b; }
QTabBar::tab:selected { color: #2445b8; border-bottom: 2px solid #315cf5; font-weight: 600; }
QTabBar::tab:hover { background: #eaf0ff; }
"""
