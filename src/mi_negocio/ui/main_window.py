from pathlib import Path
from ..branding import app_icon
from ..storage import StorageError
from ..version import APP_NAME, DISPLAY_VERSION

from PySide6.QtCore import Qt,QDate,QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QPushButton, QStackedWidget, QButtonGroup, QScrollArea,
)

from .catalog_page import CatalogPage
from .preferences import DisplayPreferences
from .home_page import HomePage
from .settings_page import SettingsPage
from .sales_page import SalesPage
from .purchases_page import PurchasesPage
from ..purchases_repository import PurchasesRepository
from ..settings_repository import SettingsRepository
from ..sales_repository import SalesRepository
from .icons import icon
from .style import STYLE, PALETTE


class MainWindow(QMainWindow):
    def __init__(self, repository, logo_path: Path | None = None, preferences=None):
        super().__init__()
        self.setWindowTitle(APP_NAME + ' · Inicio')
        self.setWindowIcon(app_icon())
        available = self.screen().availableGeometry()
        self.resize(min(1440, max(800, available.width() - 24)),
                    min(900, max(560, available.height() - 48)))
        self.setMinimumSize(800, 560)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(130)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(10, 16, 10, 12)
        logo = QPixmap(str(logo_path)) if logo_path and logo_path.is_file() else QPixmap()
        if not logo.isNull():
            label = QLabel()
            label.setPixmap(logo.scaled(112, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            label = QLabel()
            label.setAccessibleName('Nimbo')
            label.setPixmap(app_icon().pixmap(56,56))
            label.setFixedSize(56,56)
            label.setAlignment(Qt.AlignCenter)
        side.addWidget(label, alignment=Qt.AlignHCenter)
        brand = QLabel('Mi negocio')
        brand.setObjectName('sidebarBrand')
        brand.setAlignment(Qt.AlignCenter)
        side.addWidget(brand)
        side.addSpacing(4)
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_content = QWidget()
        nav_content.setObjectName('navContent')
        nav_layout = QVBoxLayout(nav_content)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(3)
        self.nav_buttons = {}
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for key, title, enabled in [('home', 'Inicio', True), ('sales', 'Ventas', True),
            ('purchases', 'Compras', True), ('expenses', 'Gastos', True), ('inventory', 'Inventario', True), ('catalog', 'Productos', True),
            ('money', 'Dinero', True), ('reports', 'Informes', True), ('settings', 'Configuración', True)]:
            button = QPushButton()
            button.setObjectName('navButton')
            body = QVBoxLayout(button)
            body.setContentsMargins(4, 6, 4, 6)
            body.setSpacing(2)
            glyph = QLabel()
            glyph.setObjectName('navIcon')
            glyph.setPixmap(icon('expense' if key=='expenses' else key, PALETTE['primary'] if enabled else '#8290a5', 20).pixmap(20, 20))
            glyph.setFixedSize(20, 20)
            caption = QLabel(title)
            caption.setObjectName('navTitle')
            caption.setAlignment(Qt.AlignCenter)
            status = QLabel('' if enabled else 'Próximamente')
            status.setObjectName('navStatus')
            status.setAlignment(Qt.AlignCenter)
            status.setFixedHeight(12)
            for child in (glyph, caption, status):
                child.setAttribute(Qt.WA_TransparentForMouseEvents)
                body.addWidget(child, alignment=Qt.AlignHCenter)
            button.setCheckable(True)
            button.setEnabled(enabled)
            button.setFixedHeight(65)
            button.setAccessibleName(title)
            if not enabled:
                button.setAccessibleDescription('Próximamente. Este módulo aún no está disponible.')
                button.setToolTip('Próximamente: ' + title)
            else:
                button.clicked.connect(lambda checked=False, page=key: self.navigate(page))
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            nav_layout.addWidget(button)
        nav_layout.addStretch()
        nav_scroll.setWidget(nav_content)
        side.addWidget(nav_scroll, 1)
        local = QLabel('Nimbo\n' + DISPLAY_VERSION + '\nEn este equipo')
        local.setObjectName('muted')
        local.setAlignment(Qt.AlignCenter)
        side.addWidget(local)
        layout.addWidget(sidebar)
        self.pages = QStackedWidget()
        self.catalog_page = CatalogPage(repository, self)
        preferences = preferences if preferences is not None else DisplayPreferences()
        settings = SettingsRepository(repository.connection)
        sales = SalesRepository(repository.connection)
        self.sales_page = SalesPage(repository, settings, sales, self, preferences)
        self.settings_page = SettingsPage(settings, self, preferences)
        from ..expenses_repository import ExpensesRepository
        from .expenses_page import ExpensesPage
        self.expenses_page=ExpensesPage(ExpensesRepository(repository.connection),settings,self)
        self.pages.addWidget(self.expenses_page)
        self.expenses_page.open_sale.connect(self.open_expense_sale)
        self.expenses_page.opening_failed.connect(self.show_sale_error)
        self.settings_page.settings_changed.connect(self.expenses_page.refresh_options)
        self.settings_page.settings_changed.connect(self.expenses_page.refresh)
        self.sales_page.sales_changed.connect(self.expenses_page.refresh)
        self.purchases_page = PurchasesPage(repository, PurchasesRepository(repository.connection), self, preferences)
        from ..inventory_repository import InventoryRepository
        from .inventory_page import InventoryPage
        self.inventory_page=InventoryPage(InventoryRepository(repository.connection),self)
        self.pages.addWidget(self.inventory_page)
        self.settings_page.settings_changed.connect(self.inventory_page.refresh)
        self.pages.addWidget(self.purchases_page)
        self.home_page = HomePage(repository, self, sales=sales, purchases_available=True, expenses_available=True)
        self.home_page.new_expense_requested.connect(self.expenses_page.open_new_expense)
        self.home_page.new_purchase_requested.connect(self.purchases_page.open_new_purchase)
        self.purchases_page.opening_failed.connect(self.show_sale_error)
        self.pages.addWidget(self.sales_page)
        self.pages.addWidget(self.settings_page)
        self.home_page.new_sale_requested.connect(self.sales_page.open_new_sale)
        self.home_page.pending_requested.connect(self.open_pending)
        self.sales_page.sales_changed.connect(self.home_page.refresh_summary)
        self.sales_page.opening_failed.connect(self.show_sale_error)
        self.settings_page.settings_changed.connect(self.sales_page.refresh_accounts)
        self.settings_page.settings_changed.connect(self.purchases_page.refresh_purchases)
        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.catalog_page)
        layout.addWidget(self.pages, 1)
        from ..money_repository import MoneyRepository
        from .money_page import MoneyPage
        self.money_page=MoneyPage(MoneyRepository(repository.connection),self)
        self.pages.addWidget(self.money_page)
        self.money_page.open_settings.connect(lambda:self.navigate('settings'))
        self.money_page.open_source.connect(self.open_money_source)
        self.money_page.changed.connect(self.home_page.refresh_summary)
        self.money_page.changed.connect(self.expenses_page.refresh)
        for signal in (self.sales_page.sales_changed,self.expenses_page.changed,self.purchases_page.purchases_changed,self.settings_page.settings_changed):
            signal.connect(self.money_page.refresh)
        self.settings_page.settings_changed.connect(self.home_page.refresh_summary)
        self.home_page.open_catalog.connect(lambda: self.navigate('catalog'))
        self.home_page.sales_period_requested.connect(self.open_home_sales)
        self.home_page.all_sales_requested.connect(lambda:self.open_home_sales(None,None))
        self.home_page.expenses_period_requested.connect(self.open_home_expenses)
        self.home_page.pending_expenses_requested.connect(self.open_home_unpaid)
        self.home_page.money_requested.connect(self.open_home_money)
        self.home_page.accounts_requested.connect(self.open_home_accounts)
        self.home_page.sale_requested.connect(self.sales_page.open_sale_detail)
        self.expenses_page.changed.connect(self.home_page.refresh_summary)

        from .reports_page import ReportsPage
        self.reports_page = ReportsPage(repository.connection, self)
        self.pages.addWidget(self.reports_page)
        self.navigate('home')

    def navigate(self, page: str) -> None:
        if page not in ('home', 'catalog', 'sales', 'settings', 'purchases', 'inventory', 'expenses', 'money', 'reports'):
            return
        target = {'home': self.home_page, 'catalog': self.catalog_page, 'sales': self.sales_page, 'settings': self.settings_page, 'purchases': self.purchases_page, 'inventory': self.inventory_page, 'expenses': self.expenses_page,'money':self.money_page, 'reports':self.reports_page}[page]
        self.pages.setCurrentWidget(target)
        self.catalog_page.new_shortcut.setEnabled(page == 'catalog')
        self.sales_page.new_shortcut.setEnabled(page == 'sales')
        self.purchases_page.new_shortcut.setEnabled(page == 'purchases')
        self.nav_buttons[page].setChecked(True)
        self.setWindowTitle(APP_NAME + ' · ' + {'home': 'Inicio', 'catalog': 'Catálogo de productos y servicios', 'sales': 'Ventas', 'settings': 'Configuración', 'purchases': 'Compras', 'inventory': 'Inventario', 'expenses': 'Gastos','money':'Dinero', 'reports':'Informes'}[page])
        if page == 'reports':self.reports_page.refresh()
        if page == 'money':self.money_page.refresh()
        if page == 'expenses':
            self.expenses_page.refresh_options();self.expenses_page.refresh()
        if page == 'inventory':
            self.inventory_page.refresh()
            self.inventory_page.open_setup()
        if page == 'settings':
            self.settings_page.card_settings.refresh()
            self.settings_page.purchase_concepts.refresh()
            self.settings_page.account_editor.refresh()
            self.settings_page.expense_categories.refresh()
            self.settings_page.inventory_settings.refresh()
        if page == 'purchases':
            self.purchases_page.refresh_purchases()
        if page == 'home':
            self.home_page.refresh_summary()

    def open_money_source(self,origin,key):
        if origin=='sale':self.open_expense_sale(key)
        elif origin=='expense':self.expenses_page._open_dialog(key)
        elif origin=='loan':
            self.navigate('expenses');self.expenses_page.tabs.setCurrentIndex(2);self.expenses_page.loans.select_loan(key)

    def open_expense_sale(self,key):
        from .sale_detail_dialog import SaleDetailDialog
        try:
            dialog=SaleDetailDialog(key,self.sales_page.settings,self.sales_page.sales,self)
            self.expenses_page.sale_dialog=dialog
            dialog.saved.connect(self.sales_page.changed)
            dialog.show()
        except StorageError as error:self.expenses_page.error.setText(str(error))

    def offer_inventory_setup(self):
        try:
            if not self.inventory_page.repository.state()['initialized']:
                self.navigate('inventory')
        except StorageError as error:self.show_sale_error(str(error))

    def open_home_sales(self,start,end):
        self.navigate('sales');self.sales_page.show_period(start,end)

    def open_home_expenses(self,start,end):
        self.navigate('expenses');self.expenses_page.show_period(start,end)

    def open_home_unpaid(self):
        from datetime import date
        self.navigate('expenses');self.expenses_page.show_period(date(1900,1,1),date.today(),pending=True)

    def open_home_money(self):
        self.navigate('money');page=self.money_page;today=QDate.currentDate()
        controls=(page.account_filter,page.period.custom,page.period.start,page.period.end)
        for control in controls:control.blockSignals(True)
        page.account_filter.setCurrentIndex(0);page.period.custom.setChecked(True)
        page.period.start.setDate(QDate(today.year(),today.month(),1));page.period.end.setDate(today)
        for control in controls:control.blockSignals(False)
        page.tabs.setCurrentIndex(0);page.period._update()

    def open_home_accounts(self):
        self.open_home_money();self.money_page.tabs.setCurrentIndex(2)

    def open_pending(self):
        self.navigate('sales')
        self.sales_page.show_pending()

    def show_sale_error(self, message):
        if self.pages.currentWidget() is self.home_page:
            self.home_page.error_label.setText(message)
            self.home_page.error_label.show()
            self.home_page.retry_button.show()
            QTimer.singleShot(0,lambda:self.home_page.scroll.ensureWidgetVisible(self.home_page.error_label))
