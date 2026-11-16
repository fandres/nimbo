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
    open_catalog = Signal()
    new_sale_requested = Signal()
    pending_requested = Signal()
    new_purchase_requested = Signal()
    new_expense_requested = Signal()

    def __init__(self, repository, parent=None, sales=None, purchases_available=False, expenses_available=False):
        super().__init__(parent)
        self.repository = repository
        self.sales = sales
        self._compact = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setObjectName('homeContent')
        self.scroll.setWidget(content)
        root.addWidget(self.scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 18, 24, 14)
        layout.setSpacing(9)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(5)
        self.date_label = label('')
        heading.addWidget(self.date_label)
        heading.addWidget(label('Tu negocio, de un vistazo', 'homeTitle'))
        heading.addWidget(label('Lo importante, en un solo lugar.'))
        header.addLayout(heading, 1)
        sale_area = QVBoxLayout()
        new_sale = QPushButton('+ Nueva venta')
        self.new_sale_button = new_sale
        new_sale.setObjectName('homeNewSale')
        new_sale.setMinimumSize(260, 64)
        new_sale.setCursor(Qt.PointingHandCursor)
        new_sale.setAccessibleDescription('Abrir el formulario para registrar una nueva venta.')
        new_sale.setEnabled(sales is not None)
        new_sale.clicked.connect(self.new_sale_requested.emit)
        sale_area.addWidget(new_sale)
        header.addLayout(sale_area)
        layout.addLayout(header)
        self.hero_grid = QGridLayout()
        self.hero_grid.setSpacing(18)
        self.hero, hero = card('Ventas del mes', hero=True)
        self.sales_total = label('Aún sin registros de ventas', 'heroValue')
        self.sales_shipping = label('Productos y servicios; envío cobrado por separado.', 'heroHelp')
        hero.addWidget(self.sales_total)
        hero.addWidget(self.sales_shipping)
        hero.addStretch()
        self.money, money = card('Tu dinero')
        self.cash_balance=label('Saldo aún no disponible', 'sectionValue');money.addWidget(self.cash_balance)
        self.cash_notice=label('Faltan saldos iniciales y los demás movimientos.');money.addWidget(self.cash_notice)
        self.pending_total = label('Por cobrar · Próximamente')
        money.addWidget(self.pending_total)
        self.hero_grid.addWidget(self.hero, 0, 0)
        self.hero_grid.addWidget(self.money, 0, 1)
        layout.addLayout(self.hero_grid)
        self.action_grid = QGridLayout()
        self.action_grid.setSpacing(14)
        self.action_cards = []
        self.future_actions = [] if sales else [new_sale]
        for glyph, title, description in [
            ('plus', 'Vender', 'Registra una nueva venta.'),
            ('purchases', 'Comprar o importar', 'Registra compras y costos.'),
            ('expense', 'Anotar un gasto', 'Organiza los gastos del negocio.'),
            ('clock', 'Cobrar', 'Consulta los cobros pendientes.'),
        ]:
            available = (sales is not None and glyph in ('plus', 'clock')) or (purchases_available and glyph == 'purchases') or (expenses_available and glyph == 'expense')
            frame = HomeAction()
            frame.setObjectName('homeAction')
            frame.setProperty('action', glyph)
            frame.setEnabled(available)
            frame.setCursor(Qt.PointingHandCursor if available else Qt.ArrowCursor)
            frame.setAccessibleName(title)
            frame.setAccessibleDescription(description if available else 'Próximamente. Esta acción aún no está disponible.')
            frame.setToolTip(description)
            body = QVBoxLayout(frame)
            body.setContentsMargins(18, 14, 18, 14)
            body.setSpacing(6)
            color = HOME_ACTION_COLORS[glyph]
            badge = QLabel()
            badge.setPixmap(icon(glyph, color, 22).pixmap(22, 22))
            body.addWidget(badge)
            title_label = label(title, 'homeActionTitle')
            title_label.setStyleSheet('color: ' + color + '; font-weight: 700;')
            body.addWidget(title_label)
            body.addWidget(label(description))
            body.addStretch()
            body.addWidget(label('Abrir  →' if available else 'Próximamente', 'coming'), alignment=Qt.AlignLeft)
            # A single button owns the entire hit area, including its text and icon.
            for child in frame.findChildren(QLabel):
                child.setAttribute(Qt.WA_TransparentForMouseEvents)
            if available:
                frame.clicked.connect({'plus': self.new_sale_requested.emit, 'clock': self.pending_requested.emit, 'purchases': self.new_purchase_requested.emit, 'expense': self.new_expense_requested.emit}[glyph])
            else:
                self.future_actions.append(frame)
            self.action_cards.append(frame)
        layout.addLayout(self.action_grid)
        self.detail_grid = QGridLayout()
        self.detail_grid.setSpacing(18)
        self.today, today = card('Para hoy')
        counts = QHBoxLayout()
        self.products_count = label('—', 'countValue')
        self.services_count = label('—', 'countValue')
        for number, title in [(self.products_count, 'Productos activos'), (self.services_count, 'Servicios activos')]:
            group = QHBoxLayout()
            group.addWidget(number)
            group.addWidget(label(title))
            counts.addLayout(group)
        today.addLayout(counts)
        today.addWidget(label('Son registros del catálogo; no existencias de inventario.'))
        self.error_label = label('', 'error')
        self.error_label.hide()
        today.addWidget(self.error_label)
        self.retry_button = QPushButton('Reintentar')
        self.retry_button.hide()
        self.retry_button.clicked.connect(self.refresh_summary)
        today.addWidget(self.retry_button)
        self.catalog_button = QPushButton('Ver catálogo  →')
        self.catalog_button.setObjectName('link')
        self.catalog_button.clicked.connect(self.open_catalog.emit)
        today.addWidget(self.catalog_button)
        self.cash, cash = card('Flujo de caja neto')
        cash.addWidget(label('Consulta el gráfico y los movimientos de tus cuentas en Dinero.'))
        cash.addWidget(label('Flujo neto = cobros recibidos − pagos realizados.'))
        cash.addStretch()
        legend = QHBoxLayout()
        for text, color in [('Positivo · verde', PALETTE['positive']),
                            ('Cerca de cero · ámbar', PALETTE['near_zero']),
                            ('Negativo · rojo', PALETTE['negative'])]:
            state = label(text)
            state.setStyleSheet('color: ' + color)
            legend.addWidget(state)
        cash.addLayout(legend)
        layout.addLayout(self.detail_grid)
        self.recent_sales, recent = card('Tus últimas ventas')
        self.recent_text = label('Cuando registres tus primeras ventas, podrás consultarlas aquí.')
        recent.addWidget(self.recent_text)
        layout.addWidget(self.recent_sales)
        layout.addWidget(label('Tus datos se guardan en este equipo.'))
        layout.addStretch()
        self._arrange(False)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(60000)
        self.refresh_timer.timeout.connect(lambda: self.refresh_summary() if self.isVisible() else None)
        self.refresh_timer.start()

    def _arrange(self, compact):
        if self._compact == compact:
            return
        self._compact = compact
        for grid in (self.hero_grid, self.action_grid, self.detail_grid):
            while grid.count():
                grid.takeAt(0)
            for column in range(4):
                grid.setColumnStretch(column, 0)
        self.hero_grid.addWidget(self.hero, 0, 0)
        self.hero_grid.addWidget(self.money, 1 if compact else 0, 0 if compact else 1)
        self.hero_grid.setColumnStretch(0, 3)
        if not compact:
            self.hero_grid.setColumnStretch(1, 2)
        columns = 2 if compact else 4
        for index, frame in enumerate(self.action_cards):
            self.action_grid.addWidget(frame, index // columns, index % columns)
        for column in range(columns):
            self.action_grid.setColumnStretch(column, 1)
        self.detail_grid.addWidget(self.today, 0, 0)
        self.detail_grid.addWidget(self.cash, 1 if compact else 0, 0 if compact else 1)
        self.detail_grid.setColumnStretch(0, 1)
        if not compact:
            self.detail_grid.setColumnStretch(1, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange(self.width() < 920)

    def refresh_summary(self):
        self.date_label.setText(QLocale(QLocale.Spanish, QLocale.Colombia).toString(QDate.currentDate(), "dddd d 'de' MMMM"))
        try:
            from ..money_repository import MoneyRepository
            from ..credit_cards import CreditCardsRepository
            cash=MoneyRepository(self.repository.connection).summary(date.today().replace(day=1),date.today())
            self.cash_balance.setText(format_cop(cash['available']))
            messages=([f"Saldo parcial · {cash['missing']} cuentas sin configurar"] if cash['missing'] else ['Efectivo y bancos · disponible hoy'])
            cards=CreditCardsRepository(self.repository.connection)
            messages.extend(n['text'] for n in cards.reminders())
            self.cash_notice.setText('\n'.join(messages))
            products = self.repository.list_products(active=True)
            summary = self.sales.home_summary(date.today()) if self.sales else None
        except StorageError as error:
            self.sales_total.setText('No disponible')
            self.pending_total.setText('Cobros no disponibles')
            self.recent_text.setText('No se pudieron consultar las ventas.')
            self.products_count.setText('—')
            self.services_count.setText('—')
            self.error_label.setText(str(error))
            self.error_label.show()
            self.retry_button.show()
            return
        self.products_count.setText(str(sum(p.kind == 'product' for p in products)))
        self.services_count.setText(str(sum(p.kind == 'service' for p in products)))
        self.error_label.clear()
        self.error_label.hide()
        self.retry_button.hide()

        if summary is not None:
            self.sales_total.setText(format_cop(summary['month_subtotal_cents']))
            self.sales_shipping.setText('Productos y servicios · Envío cobrado: ' + format_cop(summary['month_shipping_cents']))
            self.pending_total.setText(f"Por cobrar: {format_cop(summary['pending_total_cents'])} · {summary['pending_count']} pendientes")
            self.recent_text.setText('\n'.join(f"{s['sold_on']} · {s['invoice_ref'] or '#' + str(s['id'])} · {s['method_name']} · {format_cop(s['total_cents'])} · {'Recibido' if s['received'] else 'Pendiente'}" for s in summary['recent_sales']) or 'Aún no has registrado ventas.')
