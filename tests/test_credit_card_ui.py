from datetime import date
import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QMessageBox
from mi_negocio.repository import CatalogRepository
from mi_negocio.credit_cards import CreditCardsRepository
from mi_negocio.money_repository import MoneyRepository
from mi_negocio.ui.credit_card_dialogs import CardDialog, CardSettingsWidget, CardDetailDialog


@pytest.fixture
def cards(tmp_path):
    catalog = CatalogRepository(tmp_path / 'cards-ui.db')
    yield CreditCardsRepository(catalog.connection), MoneyRepository(catalog.connection)
    catalog.close()


def test_settings_default_off_and_optional_card_fields(qtbot, cards):
    repo, money = cards
    widget = CardSettingsWidget(repo); qtbot.addWidget(widget)
    assert not widget.enabled.isChecked() and not widget.add.isEnabled()
    widget.enabled.setChecked(True)
    dialog = CardDialog(repo); qtbot.addWidget(dialog)
    dialog.persist()
    assert dialog.name.property('invalid')
    dialog.name.setText('Visa sin corte'); dialog.persist()
    assert dialog.result() == QDialog.Accepted
    card = repo.list_cards()[0]
    assert card['cut_day'] is None and card['rate'] == '' and card['remind_days'] == 0
    widget.refresh()
    assert widget.table.rowCount() == 1
    edit = CardDialog(repo, card['id']); qtbot.addWidget(edit)
    edit.rate.setText('2,5'); edit.rate_unit.setCurrentIndex(1); edit.persist()
    assert repo.get(card['id'])['rate'] == '2.5'


def test_real_charges_reconciliation_and_disabled_visibility(qtbot, cards):
    repo, money = cards; repo.set_enabled(True)
    card = repo.save_card('Visa')
    money.set_opening(card['account_id'], date(2020, 1, 1), -10000)
    dialog = CardDetailDialog(repo, card['id']); qtbot.addWidget(dialog)
    assert dialog.charged_on.calendarPopup() and dialog.start.calendarPopup()
    dialog.persist_charge()
    assert dialog.interest.property('invalid')
    dialog.charged_on.setDate(QDate(2020, 1, 15))
    dialog.interest.setText('10,00'); dialog.fee.setText('2,00'); dialog.persist_charge()
    assert repo.debt(card['id'])['total_cents'] == 11200
    assert dialog.charges.rowCount() == 1
    dialog.start.setDate(QDate(2020, 1, 1)); dialog.end.setDate(QDate(2020, 1, 31))
    dialog.confirmed_debt.setText('112,00'); dialog.persist_reconciliation()
    assert dialog.error.text() == ''
    assert not repo.periods(card['id'])[0]['provisional']
    assert dialog.periods.rowCount() == 1
    repo.set_enabled(False); dialog.refresh()
    assert not dialog.save_charge.isEnabled() and not dialog.reconcile.isEnabled()
    assert dialog.charges.rowCount() == 1 and dialog.periods.rowCount() == 1
    assert 'desactivado' in dialog.status.text()


def test_disable_with_debt_requires_warning(qtbot, cards, monkeypatch):
    repo, money = cards; repo.set_enabled(True)
    card = repo.save_card('Visa'); money.set_opening(card['account_id'], date(2020, 1, 1), -10000)
    widget = CardSettingsWidget(repo); qtbot.addWidget(widget)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.No)
    widget.enabled.setChecked(False)
    assert repo.enabled() and widget.enabled.isChecked()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    widget.enabled.setChecked(False)
    assert not repo.enabled() and widget.table.rowCount() == 1


def test_zero_interest_period_and_stale_revision(qtbot, cards):
    repo, money = cards; repo.set_enabled(True)
    card = repo.save_card('Visa'); money.set_opening(card['account_id'], date(2020, 1, 1), 0)
    dialog = CardDetailDialog(repo, card['id']); qtbot.addWidget(dialog)
    dialog.start.setDate(QDate(2020, 1, 1)); dialog.end.setDate(QDate(2020, 1, 31))
    repo.save_card('Visa editada', card_id=card['id'], expected_revision=card['revision'])
    dialog.persist_reconciliation()
    assert dialog.error.text() and not repo.periods(card['id'])
    dialog.refresh(); dialog.persist_reconciliation()
    assert not repo.periods(card['id'])[0]['provisional']


def test_cancel_charge_preserves_history_and_reopens_period(qtbot, cards, monkeypatch):
    repo, money = cards; repo.set_enabled(True)
    card = repo.save_card('Visa'); money.set_opening(card['account_id'], date(2020, 1, 1), 0)
    repo.charge(card['id'], date(2020, 1, 15), 100, 0, request_id='real-charge')
    repo.reconcile(card['id'], date(2020, 1, 1), date(2020, 1, 31), 100,
                   expected_revision=repo.get(card['id'])['revision'])
    dialog = CardDetailDialog(repo, card['id']); qtbot.addWidget(dialog)
    dialog.charges.selectRow(0)
    monkeypatch.setattr('mi_negocio.ui.credit_card_dialogs.required_reason', lambda *args: ('Cargo duplicado', True))
    dialog.cancel_selected_charge()
    assert repo.list_charges(card['id'])[0]['cancellation_reason'] == 'Cargo duplicado'
    assert repo.periods(card['id'])[0]['provisional']
    assert dialog.charges.item(0, 3).text() == 'Anulado'
