from datetime import date
from PySide6.QtCore import Qt
from mi_negocio.repository import CatalogRepository
from mi_negocio.money_repository import MoneyRepository
from mi_negocio.credit_cards import CreditCardsRepository
from mi_negocio.ui.money_page import MoneyPage
from mi_negocio.ui.money_dialogs import MoneyEntryDialog,OpeningDialog
from mi_negocio.ui.main_window import MainWindow


def test_money_navigation_opening_transfer_and_validation(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');w=MainWindow(cat);qtbot.addWidget(w);w.show();w.navigate('money');p=w.money_page
    assert w.pages.currentWidget() is p
    assert p.tabs.count()==3 and not p.error.text()
    p.tabs.setCurrentIndex(2);p.accounts_table.selectRow(0);p.opening();d=p.dialog;qtbot.addWidget(d);d.value.setText('100');d.save()
    assert p.accounts[0]['balance_cents']==10000
    p.new_entry('transfer');d=p.dialog;qtbot.addWidget(d);d.save()
    assert d.concept.property('invalid')
    d.concept.setText('Traslado');d.value.setText('25');d.source.setCurrentIndex(d.source.findData(1));d.destination.setCurrentIndex(d.destination.findData(2));d.save()
    assert not d.isVisible()
    assert p.accounts[0]['balance_cents']==7500
    assert p.repository.summary(date.today(),date.today())['net']==0
    w.close();cat.close()


def test_card_payment_form_does_not_double_expense(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');r=MoneyRepository(cat.connection);cards=CreditCardsRepository(cat.connection);cards.set_enabled(True);card=cards.save_card('Visa');today=date.today()
    r.set_opening(card['account_id'],today,-10000);r.set_opening(2,today,50000)
    cards.charge(card['id'],today,200,0,request_id='charge')
    d=MoneyEntryDialog(r,kind='card_payment',card_account=card['account_id']);qtbot.addWidget(d);d.show()
    d.concept.setText('Abono');d.source.setCurrentIndex(d.source.findData(2));d.capital.setText('50');d.interest.setText('2');d.save()
    assert not d.error.text()
    assert cards.debt(card['id'])['total_cents']==5000
    assert r.summary(today,today)['outgoing']==5200
    cat.close()


def test_summary_not_blank_and_no_scroll_at_desktop(qtbot,tmp_path):
    from PySide6.QtWidgets import QScrollArea
    cat=CatalogRepository(tmp_path/'db');p=MoneyPage(MoneyRepository(cat.connection));qtbot.addWidget(p);p.resize(1300,900);p.show();qtbot.wait(20)
    scroll=p.tabs.widget(0)
    assert isinstance(scroll,QScrollArea)
    assert scroll.verticalScrollBar().maximum()==0
    assert 'sin saldo inicial' in p.warning.text()
    cat.close()


def test_disabled_cards_are_not_offered_in_general_form(qtbot, tmp_path):
    cat = CatalogRepository(tmp_path / 'db')
    d = MoneyEntryDialog(MoneyRepository(cat.connection))
    qtbot.addWidget(d)
    assert d.kind.findData('card_payment') == -1
    cat.close()


def test_historical_closing_and_signed_opening_are_visible(qtbot, tmp_path):
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QTextEdit
    from mi_negocio.ui.style import format_cop
    cat = CatalogRepository(tmp_path / 'db')
    r = MoneyRepository(cat.connection)
    r.set_opening(2, date(2020, 1, 1), -10000)
    r.add('contribution', date(2020, 2, 1), 30000, 'Aporte', to_account=2, request_id='feb')
    p = MoneyPage(r)
    qtbot.addWidget(p)
    p.period.custom.setChecked(True)
    p.period.start.setDate(QDate(2020, 1, 1))
    p.period.end.setDate(QDate(2020, 1, 31))
    p.refresh()
    row = next(i for i, a in enumerate(p.accounts) if a['id'] == 2)
    assert p.accounts_table.item(row, 3).text() == format_cop(-10000)
    assert p.accounts_table.item(row, 4).text() == format_cop(20000)
    assert p.accounts_table.item(row, 5).text() == format_cop(-10000)
    p.accounts_table.selectRow(row)
    p.account_history()
    qtbot.addWidget(p.detail)
    history = p.detail.findChild(QTextEdit).toPlainText()
    assert '2020-01-01' in history and format_cop(-10000) in history
    cat.close()
