"""Independent read-only report filters, preview and atomic PDF export."""
from calendar import monthrange
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QSignalBlocker
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QComboBox, QLineEdit, QPushButton, QTextBrowser, QFileDialog,
    QMessageBox, QFrame)

from ..storage import StorageError
from ..catalog import ValidationError
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

TITLES = {'sales': 'Ventas', 'expenses': 'Gastos', 'money': 'Dinero', 'profitability': 'Rentabilidad'}


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
    def __init__(self, kind, connection, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.settings = SettingsRepository(connection)
        self.sales = SalesRepository(connection)
        self.expenses = ExpensesRepository(connection)
        self.money = MoneyRepository(connection)
        self.profitability = ProfitabilityRepository(connection)
        self.html = ''
        self.rows = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        filters = QFrame()
        filters.setObjectName('saleSection')
        grid = QGridLayout(filters)
        grid.setContentsMargins(14, 10, 14, 12)
        grid.addWidget(note('Filtros del informe', 'cardTitle'), 0, 0, 1, 4)
        today = date.today()
        self.month = combo([(name, i) for i, name in enumerate(MONTHS, 1)] + [('Personalizado', None)])
        self.month.setCurrentIndex(today.month-1)
        self.year = combo([(str(y), y) for y in range(today.year, today.year-6, -1)] + [('Más años…', None)])
        self.selected_year = today.year
        self.start, self.end = date_edit(), date_edit()
        self.start.setDate(QDate(today.year, today.month, 1))
        self.end.setDate(QDate.currentDate())
        for col, (label, field) in enumerate([('Mes', self.month), ('Año', self.year), ('Desde', self.start), ('Hasta', self.end)]):
            grid.addWidget(note(label), 1, col)
            grid.addWidget(field, 2, col)
            field.setAccessibleName(label)
            grid.setColumnStretch(col, 1)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('Buscar cliente, producto o factura…' if kind in ('sales', 'profitability') else 'Buscar concepto o plataforma…' if kind=='expenses' else 'Buscar concepto o cuenta…')
        self.search.setAccessibleName('Búsqueda del informe')
        self.account = combo([('Todas las cuentas', None)])
        self.account.setAccessibleName('Cuenta')
        grid.addWidget(self.search, 3, 0, 1, 4 if kind=='profitability' else 2)
        if kind!='profitability':
            grid.addWidget(self.account, 3, 2, 1, 2)
        self.state = combo([('Todos los estados', None), ('Recibido' if kind=='sales' else 'Pagado / a tarjeta', True), ('Pendiente', False)])
        self.validity = combo([('Vigentes', False), ('Anulados', True), ('Todos', None)])
        self.withholding = combo([('Todas las retenciones', None), ('Con retención', True), ('Sin retención', False)])
        self.category = combo([('Todas las categorías', None)])
        self.platform = combo([('Todas las plataformas y gastos', None)])
        self.date_basis = combo([('Fecha del gasto', 'spent'), ('Fecha de pago', 'paid')])
        extras = []
        if kind=='sales':
            extras = [('Estado de cobro', self.state), ('Vigencia', self.validity), ('Retención', self.withholding)]
        elif kind=='expenses':
            extras = [('Estado', self.state), ('Vigencia', self.validity), ('Categoría', self.category), ('Comisiones de plataforma', self.platform)]
        for col, (label, field) in enumerate(extras):
            field.setAccessibleName(label)
            grid.addWidget(field, 4, col)
        if kind=='expenses':
            self.date_basis.setAccessibleName('Aplicar período a')
            grid.addWidget(self.date_basis, 5, 0, 1, 2)
        root.addWidget(filters)
        actions = QHBoxLayout()
        actions.addWidget(note('Vista previa · solo lectura'), 1)
        self.update_button = QPushButton('Actualizar')
        self.export_button = QPushButton('Exportar PDF')
        self.export_button.setObjectName('primary')
        actions.addWidget(self.update_button)
        actions.addWidget(self.export_button)
        root.addLayout(actions)
        self.error = note('', 'error')
        self.error.hide()
        self.status = note('')
        self.status.hide()
        root.addWidget(self.error)
        root.addWidget(self.status)
        self.preview = ReportPreview()
        self.preview.setOpenLinks(False)
        self.preview.setOpenExternalLinks(False)
        self.preview.setStyleSheet('QTextBrowser {background: white; border: 1px solid #e0e6f0; border-radius: 12px; padding: 16px;}')
        root.addWidget(self.preview, 1)
        self.month.currentIndexChanged.connect(self.select_month)
        self.year.currentIndexChanged.connect(self.select_year)
        self.start.dateChanged.connect(self.custom_dates)
        self.end.dateChanged.connect(self.custom_dates)
        self.search.textChanged.connect(self.refresh)
        for widget in [self.account] + [field for _, field in extras] + ([self.date_basis] if kind=='expenses' else []):
            widget.currentIndexChanged.connect(self.refresh)
        self.update_button.clicked.connect(self.refresh_options)
        self.export_button.clicked.connect(self.export_pdf)
        self.refresh_options()

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

    def refresh(self, *_):
        self.status.hide()
        try:
            month, year = self.month.currentData(), self.year.currentData()
            if month is not None and year is not None and date(year, month, 1)>date.today():
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
            elif self.kind=='profitability':
                snapshot = self.profitability.report(start, end, query)
                rows = snapshot['rows']
                html = build_profitability_report(snapshot, start, end)
            else:
                rows = self.money.movements(start, end, account, query)
                html = build_money_report(rows, start, end, self.account.currentText(), query, account)
            self.rows, self.html = rows, html
            self.preview.setHtml(html)
            self.error.clear()
            self.error.hide()
            self.export_button.setEnabled(True)
        except (StorageError, ValidationError, ValueError) as exc:
            self.fail(exc)

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
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        heading = QHBoxLayout()
        heading.addWidget(note('Informes', 'heading'))
        heading.addWidget(note('Consulta tus datos y exporta el informe del período.'), 1)
        root.addLayout(heading)
        self.tabs = QTabWidget()
        self.panels = []
        for kind, title in TITLES.items():
            panel = ReportPanel(kind, connection)
            self.panels.append(panel)
            self.tabs.addTab(panel, title)
        root.addWidget(self.tabs, 1)
        self.tabs.currentChanged.connect(self.refresh)

    def refresh(self, *_):
        self.panels[self.tabs.currentIndex()].refresh_options()
