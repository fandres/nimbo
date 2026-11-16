"""Optional credit card settings, real charges and explicit reconciliation."""
from uuid import uuid4
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QComboBox, QPushButton, QDialogButtonBox,
    QMessageBox, QTabWidget)
from ..catalog import ValidationError
from ..storage import StorageError
from ..sales import money
from .sales_widgets import note, amount, date_edit, error_text, ToggleSwitch
from .form_validation import check, required, rate_issue, amount_issue, required_reason
from .loans_page import table
from .style import format_cop
from PySide6.QtWidgets import QTableWidgetItem


def fill_table(widget, rows):
    widget.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            widget.setItem(i, j, QTableWidgetItem(str(value)))


class CardDialog(QDialog):
    def __init__(self, repository, card_id=None, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.card = repository.get(card_id) if card_id is not None else None
        self.setWindowTitle('Configurar tarjeta · Nimbo'); self.resize(780, 330)
        root = QVBoxLayout(self)
        root.addWidget(note('Tarjeta de crédito', 'cardTitle'))
        self.name = QLineEdit(); self.rate = QLineEdit()
        self.rate.setPlaceholderText('Sin tasa de referencia')
        self.rate_unit = QComboBox()
        self.rate_unit.addItem('Mensual', 'monthly'); self.rate_unit.addItem('Efectiva anual', 'effective_annual')
        self.cut_day = QComboBox(); self.cut_day.addItem('Sin día de corte', None)
        for day in range(1, 32): self.cut_day.addItem(str(day), day)
        self.remind_days = QComboBox(); self.remind_days.addItem('Desactivado', 0)
        for day in range(1, 4): self.remind_days.addItem(f'{day} día(s) antes', day)
        columns = QHBoxLayout(); left = QFormLayout(); right = QFormLayout()
        left.addRow('Nombre *', self.name); left.addRow('Tasa de referencia % · opcional', self.rate)
        left.addRow('Unidad de tasa', self.rate_unit)
        right.addRow('Día de corte · opcional', self.cut_day); right.addRow('Recordatorio · opcional', self.remind_days)
        columns.addLayout(left, 1); columns.addLayout(right, 1); root.addLayout(columns)
        root.addWidget(note('La tasa es solo una referencia: registra los intereses reales del extracto. El corte no es la fecha límite de pago. Puedes añadirlo después para habilitar los recordatorios.'))
        self.error = note('', 'error'); root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.save = buttons.button(QDialogButtonBox.Save); self.save.setText('Guardar tarjeta'); self.save.setObjectName('primary')
        buttons.button(QDialogButtonBox.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.persist); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        if self.card:
            self.name.setText(self.card['name']); self.rate.setText(self.card['rate'])
            self.rate_unit.setCurrentIndex(max(0, self.rate_unit.findData(self.card['rate_unit'])))
            self.cut_day.setCurrentIndex(max(0, self.cut_day.findData(self.card['cut_day'])))
            self.remind_days.setCurrentIndex(max(0, self.remind_days.findData(self.card['remind_days'])))
        self.cut_day.currentIndexChanged.connect(self.update_reminder)
        self.update_reminder(); self.save.setEnabled(repository.enabled())

    def update_reminder(self):
        self.remind_days.setEnabled(self.cut_day.currentData() is not None and self.repository.enabled())

    def persist(self):
        issues = [required(self.name, 'el nombre')]
        if self.rate.text().strip(): issues.append(rate_issue(self.rate, 'Tasa', 1000))
        if not check(self, issues, self.error): return
        try:
            self.repository.save_card(self.name.text(), rate=self.rate.text().replace(',', '.'),
                rate_unit=self.rate_unit.currentData(), cut_day=self.cut_day.currentData(),
                remind_days=self.remind_days.currentData() if self.cut_day.currentData() else 0,
                card_id=self.card['id'] if self.card else None,
                expected_revision=self.card['revision'] if self.card else None)
            self.accept()
        except (StorageError, ValidationError) as exc: self.error.setText(error_text(exc))


class CardSettingsWidget(QWidget):
    changed = Signal()

    def __init__(self, repository, parent=None):
        super().__init__(parent); self.repository = repository; self.rows = []
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        self.enabled = ToggleSwitch('Control de tarjetas de crédito'); root.addWidget(self.enabled)
        root.addWidget(note('Opcional. Desactivar conserva las deudas y el historial. El cupo de una tarjeta no es dinero disponible.'))
        self.table = table(['Tarjeta', 'Deuda registrada · COP', 'Corte', 'Estado']); root.addWidget(self.table)
        actions = QHBoxLayout()
        self.add = QPushButton('+ Nueva tarjeta'); self.add.setObjectName('primary')
        self.edit = QPushButton('Editar tarjeta'); self.detail = QPushButton('Ver deuda e historial')
        for button in (self.add, self.edit, self.detail): actions.addWidget(button)
        root.addLayout(actions); self.error = note('', 'error'); root.addWidget(self.error)
        self.enabled.toggled.connect(self.toggle); self.add.clicked.connect(self.new_card)
        self.edit.clicked.connect(self.edit_card); self.detail.clicked.connect(self.show_detail)
        self.refresh()

    def selected(self):
        i = self.table.currentRow()
        return self.rows[i] if 0 <= i < len(self.rows) else None

    def refresh(self):
        try:
            active = self.repository.enabled()
            self.enabled.blockSignals(True); self.enabled.setChecked(active); self.enabled.blockSignals(False)
            self.add.setEnabled(active); self.edit.setEnabled(active)
            self.rows = self.repository.list_cards(); data = []
            for card in self.rows:
                debt = self.repository.debt(card['id'])
                data.append([card['name'], format_cop(debt['total_cents']) if debt['configured'] else 'Sin saldo inicial',
                    card['cut_day'] or 'Sin configurar', 'Pendiente de conciliación' if debt['provisional'] else 'Conciliado'])
            fill_table(self.table, data)
            if self.rows: self.table.selectRow(0)
            self.error.clear()
        except (StorageError, ValidationError) as exc: self.error.setText(error_text(exc))

    def toggle(self, active):
        try:
            if not active and any((self.repository.debt(c['id'])['total_cents'] or 0) > 0 for c in self.repository.list_cards()):
                answer = QMessageBox.question(self, 'Desactivar control de tarjetas',
                    'Hay deuda pendiente. Se conservará visible junto con el historial, pero no podrás registrar operaciones hasta reactivar el control. ¿Desactivar?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes: self.refresh(); return
            self.repository.set_enabled(active); self.refresh(); self.changed.emit()
        except (StorageError, ValidationError) as exc:
            self.refresh(); self.error.setText(error_text(exc))

    def new_card(self):
        if CardDialog(self.repository, parent=self).exec(): self.refresh(); self.changed.emit()

    def edit_card(self):
        card = self.selected()
        if card and CardDialog(self.repository, card['id'], self).exec(): self.refresh(); self.changed.emit()

    def show_detail(self):
        card = self.selected()
        if card:
            dialog = CardDetailDialog(self.repository, card['id'], self)
            dialog.changed.connect(self.changed); dialog.exec(); self.refresh()


class CardDetailDialog(QDialog):
    changed = Signal()

    def __init__(self, repository, card_id, parent=None):
        super().__init__(parent); self.repository = repository; self.card_id = card_id
        self.request_id = uuid4().hex; self.charge_rows = []
        self.setWindowTitle('Deuda y extractos · Nimbo'); self.resize(940, 650)
        root = QVBoxLayout(self); self.title = note('', 'cardTitle'); root.addWidget(self.title)
        self.debt = note('', 'sectionValue'); root.addWidget(self.debt)
        self.status = note(''); root.addWidget(self.status)
        tabs = QTabWidget(); root.addWidget(tabs, 1)
        charges = QWidget(); layout = QVBoxLayout(charges)
        layout.addWidget(note('Registra únicamente intereses y cargos reales del extracto. Aumentan la deuda y aparecen en Gastos una sola vez.'))
        columns = QHBoxLayout(); left = QFormLayout(); right = QFormLayout()
        self.charged_on = date_edit(); self.interest = amount(); self.fee = amount(); self.charge_note = QLineEdit()
        left.addRow('Fecha del cargo', self.charged_on); left.addRow('Intereses · COP', self.interest)
        right.addRow('Otros cargos · COP', self.fee); right.addRow('Nota · opcional', self.charge_note)
        columns.addLayout(left, 1); columns.addLayout(right, 1); layout.addLayout(columns)
        self.save_charge = QPushButton('Guardar intereses y cargos'); self.save_charge.setObjectName('primary')
        self.save_charge.clicked.connect(self.persist_charge); layout.addWidget(self.save_charge)
        self.charges = table(['Fecha', 'Intereses · COP', 'Cargos · COP', 'Estado', 'Nota / motivo']); layout.addWidget(self.charges, 1)
        self.cancel_charge = QPushButton('Anular cargo seleccionado'); self.cancel_charge.clicked.connect(self.cancel_selected_charge); layout.addWidget(self.cancel_charge)
        tabs.addTab(charges, 'Intereses y cargos')
        reconciliation = QWidget(); layout = QVBoxLayout(reconciliation)
        layout.addWidget(note('Confirma el período después de revisar el extracto, incluso si no hubo intereses. Pagar la deuda no concilia automáticamente.'))
        columns = QHBoxLayout(); left = QFormLayout(); right = QFormLayout()
        self.start = date_edit(); self.end = date_edit(); self.start.setDate(self.start.date().addDays(1-self.start.date().day()))
        self.confirmed_debt = amount()
        left.addRow('Inicio del período', self.start); left.addRow('Cierre del período', self.end)
        right.addRow('Deuda real al cierre · COP *', self.confirmed_debt)
        columns.addLayout(left, 1); columns.addLayout(right, 1); layout.addLayout(columns)
        self.reconcile = QPushButton('Confirmar conciliación del extracto'); self.reconcile.setObjectName('primary')
        self.reconcile.clicked.connect(self.persist_reconciliation); layout.addWidget(self.reconcile)
        self.periods = table(['Desde', 'Hasta', 'Deuda confirmada · COP', 'Estado']); layout.addWidget(self.periods, 1)
        tabs.addTab(reconciliation, 'Conciliación e historial')
        self.error = note('', 'error'); root.addWidget(self.error)
        close = QPushButton('Cerrar'); close.clicked.connect(self.accept); root.addWidget(close)
        self.refresh()

    def refresh(self):
        try:
            self.card = self.repository.get(self.card_id); self.title.setText(self.card['name'])
            debt = self.repository.debt(self.card_id)
            self.debt.setText('Deuda registrada: ' + (format_cop(debt['total_cents']) if debt['configured'] else 'Sin saldo inicial'))
            self.status.setText('Pendiente de conciliación · Saldo provisional; pueden faltar intereses o cargos' if debt['provisional'] else 'Conciliado')
            self.status.setStyleSheet('color: #9a5700;' if debt['provisional'] else 'color: #167047;')
            active = self.repository.enabled() and bool(self.card['enabled'])
            for button in (self.save_charge, self.cancel_charge, self.reconcile): button.setEnabled(active)
            if not self.repository.enabled(): self.status.setText(self.status.text() + ' · Control desactivado')
            self.charge_rows = self.repository.list_charges(self.card_id)
            fill_table(self.charges, [[r['charged_on'], format_cop(r['interest_cents']), format_cop(r['fee_cents']), 'Anulado' if r['cancelled_at'] else 'Registrado', r['cancellation_reason'] or r['note']] for r in self.charge_rows])
            fill_table(self.periods, [[p['start_on'], p['end_on'], format_cop(p['confirmed_balance_cents']), 'Pendiente de conciliación' if p['provisional'] else 'Conciliado'] for p in self.repository.periods(self.card_id)])
        except (StorageError, ValidationError) as exc: self.error.setText(error_text(exc))

    def persist_charge(self):
        issues = [amount_issue(self.interest, 'Intereses'), amount_issue(self.fee, 'Otros cargos')]
        if not any(issues) and money(self.interest.text()) + money(self.fee.text()) <= 0:
            issues.append((self.interest, 'Indica un interés o cargo mayor que cero.'))
        if not check(self, issues, self.error): return
        try:
            self.repository.charge(self.card_id, self.charged_on.date().toPython(), money(self.interest.text()), money(self.fee.text()), request_id=self.request_id, note=self.charge_note.text())
            self.request_id = uuid4().hex; self.interest.setText('0,00'); self.fee.setText('0,00'); self.charge_note.clear()
            self.refresh(); self.changed.emit()
        except (StorageError, ValidationError) as exc: self.error.setText(error_text(exc))

    def persist_reconciliation(self):
        issues = [amount_issue(self.confirmed_debt, 'Deuda real al cierre')]
        if self.start.date() > self.end.date(): issues.append((self.start, 'El inicio debe ser anterior al cierre.'))
        if not check(self, issues, self.error): return
        try:
            self.repository.reconcile(self.card_id, self.start.date().toPython(), self.end.date().toPython(), money(self.confirmed_debt.text()), expected_revision=self.card['revision'])
            self.refresh(); self.changed.emit()
        except (StorageError, ValidationError) as exc: self.error.setText(error_text(exc))

    def cancel_selected_charge(self):
        i = self.charges.currentRow()
        if not 0 <= i < len(self.charge_rows) or self.charge_rows[i]['cancelled_at']: return
        reason, accepted = required_reason(self, 'Anular cargo', 'Motivo de anulación *')
        if not accepted: return
        try:
            self.repository.cancel_charge(self.charge_rows[i]['id'], reason); self.error.clear(); self.refresh(); self.changed.emit()
        except (StorageError, ValidationError) as exc: self.error.setText(error_text(exc))
