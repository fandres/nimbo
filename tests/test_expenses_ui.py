from datetime import date
from PySide6.QtCore import Qt,QDate
from mi_negocio.repository import CatalogRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.expenses_repository import ExpensesRepository
from mi_negocio.expenses import ExpenseDraft
from mi_negocio.ui.expense_dialog import ExpenseDialog
from mi_negocio.ui.expenses_page import ExpensesPage
from mi_negocio.ui.main_window import MainWindow


def test_dialog_defaults_and_save(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');r=ExpensesRepository(cat.connection)
    dialog=ExpenseDialog(r,SettingsRepository(cat.connection));qtbot.addWidget(dialog);dialog.show()
    assert dialog.paid_on.date()==QDate.currentDate()
    dialog.concept.setText('Publicidad');dialog.amount.setText('42.500')
    dialog.category.setCurrentIndex(1)
    qtbot.mouseClick(dialog.pending,Qt.LeftButton)
    assert not dialog.account.isEnabled()
    dialog.persist()
    assert r.list_movements()[0]['amount_cents']==4250000
    assert not r.list_movements()[0]['paid']
    cat.close()


def test_summary_four_recent_and_filters(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');r=ExpensesRepository(cat.connection)
    category=r.categories()[0]['id']
    for i in range(6):r.save(ExpenseDraft('Gasto '+str(i),10000,date.today(),category),request_id=str(i))
    page=ExpensesPage(r,SettingsRepository(cat.connection));qtbot.addWidget(page);page.show()
    assert page.recent.rowCount()==4
    assert page.table.rowCount()==6
    page.search.setText('Gasto 3')
    assert page.table.rowCount()==1
    assert page.filtered_summary['total_cents']==10000
    assert page.summary_data['total_cents']==60000
    page.show_all_movements()
    assert page.table.rowCount()==6 and page.tabs.currentIndex()==1
    cat.close()


def test_navigation_settings_and_home_expense_action(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');window=MainWindow(cat);qtbot.addWidget(window);window.show()
    window.navigate('expenses')
    assert window.pages.currentWidget() is window.expenses_page
    assert window.nav_buttons['expenses'].isChecked()
    assert window.settings_page.expense_categories is not None
    window.home_page.new_expense_requested.emit()
    assert window.expenses_page.dialog.isVisible()
    window.expenses_page.dialog.close();window.close();cat.close()


def test_categories_shortcuts_edit_and_disable(qtbot,tmp_path):
    from mi_negocio.ui.expense_categories import ExpenseCategoriesEditor
    cat=CatalogRepository(tmp_path/'db');r=ExpensesRepository(cat.connection)
    editor=ExpenseCategoriesEditor(r);qtbot.addWidget(editor)
    editor.name.setText('Mantenimiento CNC');editor.persist()
    key=editor.key;assert key
    dialog=ExpenseDialog(r,SettingsRepository(cat.connection));qtbot.addWidget(dialog)
    dialog.category.setCurrentIndex(dialog.category.findData(key))
    assert not any(b.isChecked() for b in dialog.category_buttons)
    editor.enabled.setChecked(False);editor.persist()
    assert key not in [c['id'] for c in r.categories()]
    cat.close()


def test_mark_paid_prefills_preserves_amount_and_history(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');r=ExpensesRepository(cat.connection)
    row=r.save(ExpenseDraft('PILA',52000000,date.today(),r.categories()[0]['id']),request_id='pending')
    dialog=ExpenseDialog(r,SettingsRepository(cat.connection),expense_id=row['id'],mark_paid=True);qtbot.addWidget(dialog)
    assert dialog.paid.isChecked() and dialog.paid_on.date()==QDate.currentDate()
    dialog.account.setCurrentIndex(dialog.account.findData(1));dialog.persist()
    assert r.get(row['id'])['amount_cents']==52000000
    assert r.get(row['id'])['paid_on']==str(date.today())
    assert len(r.history(row['id']))==2
    cat.close()


def test_summary_uses_shared_account_not_hidden_detail_filters(qtbot,tmp_path):
    from datetime import timedelta
    cat=CatalogRepository(tmp_path/'db');r=ExpensesRepository(cat.connection);category=r.categories()[0]['id']
    r.save(ExpenseDraft('Paid',10000,date.today(),category,date.today(),1),request_id='p')
    r.save(ExpenseDraft('Pending',5000,date.today(),category),request_id='n')
    page=ExpensesPage(r,SettingsRepository(cat.connection));qtbot.addWidget(page)
    page.state.setCurrentIndex(2)
    assert page.filtered_summary['total_cents']==5000 and page.summary_data['total_cents']==15000
    page.account.setCurrentIndex(page.account.findData(1))
    assert page.summary_data['total_cents']==10000 and page.filtered_summary['total_cents']==0
    page.period.custom.setChecked(True);page.period.start.setDate(QDate.currentDate());page.period.end.setDate(QDate.currentDate().addDays(-1))
    assert page.table.rowCount()==0 and page.recent.rowCount()==0 and page.error.text()
    cat.close()


def test_form_all_options_fit_and_date_click_opens_calendar(qtbot,tmp_path):
    from PySide6.QtWidgets import QScrollArea
    cat=CatalogRepository(tmp_path/'db');r=ExpensesRepository(cat.connection)
    dialog=ExpenseDialog(r,SettingsRepository(cat.connection));qtbot.addWidget(dialog);dialog.resize(1120,780);dialog.show()
    dialog.pending.click();dialog.has_due.setChecked(True);dialog.more.setChecked(True);qtbot.wait(20)
    scroll=dialog.findChild(QScrollArea)
    assert scroll.verticalScrollBar().maximum()==0
    qtbot.mouseClick(dialog.spent_on.lineEdit(),Qt.LeftButton)
    qtbot.waitUntil(lambda:dialog.spent_on.calendarWidget().isVisible())
    dialog.spent_on.calendarWidget().window().hide();dialog.close();cat.close()


def test_compare_zero_base_and_exact_percent():
    from mi_negocio.ui.expenses_page import change_text
    assert change_text(200000,250000)=='-20,0 %'
    assert change_text(10000,0)=='Sin base de comparación'
    assert change_text(0,0)=='Sin gastos en ambos períodos'


def test_concept_completion_after_three_characters_sets_category_not_amount(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');r=ExpensesRepository(cat.connection)
    category=r.categories()[1]['id']
    r.save(ExpenseDraft('Facebook publicidad',10000,date.today(),category),request_id='facebook')
    dialog=ExpenseDialog(r,SettingsRepository(cat.connection));qtbot.addWidget(dialog);dialog.show()
    dialog.amount.setText('999');dialog.concept.setFocus()
    qtbot.keyClicks(dialog.concept,'fa')
    assert not dialog.concept.suggestions.popup().isVisible()
    qtbot.keyClicks(dialog.concept,'c')
    qtbot.waitUntil(lambda:dialog.concept.suggestions.popup().isVisible())
    assert dialog.category.currentData() is None
    qtbot.keyClick(dialog.concept.suggestions.popup(),Qt.Key_Return)
    assert dialog.concept.text()=='Facebook publicidad'
    assert dialog.category.currentData()==category
    assert dialog.amount.text()=='999'
    assert dialog.isVisible() and len(r.list_movements())==1
    dialog.close();cat.close()


def test_concept_click_completion_and_short_query_hides(qtbot,tmp_path):
    cat=CatalogRepository(tmp_path/'db');r=ExpensesRepository(cat.connection);category=r.categories()[1]['id']
    r.save(ExpenseDraft('Facebook Ads',10000,date.today(),category),request_id='ads')
    dialog=ExpenseDialog(r,SettingsRepository(cat.connection));qtbot.addWidget(dialog);dialog.show();dialog.concept.setFocus()
    qtbot.keyClicks(dialog.concept,'fac');popup=dialog.concept.suggestions.popup()
    qtbot.waitUntil(popup.isVisible)
    qtbot.keyClick(popup,Qt.Key_Backspace)
    assert dialog.concept.text()=='fa' and not popup.isVisible()
    qtbot.keyClicks(dialog.concept,'ce')
    qtbot.waitUntil(popup.isVisible)
    index=dialog.concept.suggestions.completionModel().index(0,0)
    qtbot.mouseClick(popup.viewport(),Qt.LeftButton,pos=popup.visualRect(index).center())
    assert dialog.concept.text()=='Facebook Ads' and dialog.category.currentData()==category
    assert dialog.isVisible()
    dialog.close();cat.close()
