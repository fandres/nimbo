from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QLabel, QComboBox
from mi_negocio.ui.form_validation import check, required, amount_issue, choice


def test_all_errors_marked_first_focused_and_cleared_on_edit(qtbot):
    dialog=QDialog();box=QVBoxLayout(dialog)
    name=QLineEdit();amount=QLineEdit('0,00');error=QLabel()
    for w in (name,amount,error):box.addWidget(w)
    qtbot.addWidget(dialog);dialog.show();dialog.activateWindow();qtbot.wait(20)
    assert not check(dialog,[required(name,'el concepto'),amount_issue(amount,'Valor',True)],error)
    assert name.hasFocus() and name.property('invalid') and amount.property('invalid')
    name.setText('Meta');assert not name.property('invalid')
    assert not check(dialog,[required(name,'el concepto'),amount_issue(amount,'Valor',True)],error)
    assert amount.hasFocus() and amount.selectedText()=='0,00'
    assert 'Valor' in error.text() and 'concepto' not in error.text()
    amount.setText('100');assert not amount.property('invalid')
    assert check(dialog,[amount_issue(amount,'Valor',True)],error)


def test_optional_zero_and_reveal(qtbot):
    dialog=QDialog();box=QVBoxLayout(dialog);field=QComboBox();field.addItem('Selecciona',None);box.addWidget(field)
    qtbot.addWidget(dialog);dialog.show();field.hide()
    field._validation_reveal=field.show
    assert not check(dialog,[choice(field,'una cuenta')])
    assert field.isVisible() and field.property('invalid')
    assert amount_issue(QLineEdit('0'),'Envío') is None


def test_expense_missing_amount_focus_and_pending_optional_account(qtbot,tmp_path):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.expenses_repository import ExpensesRepository
    from mi_negocio.settings_repository import SettingsRepository
    from mi_negocio.ui.expense_dialog import ExpenseDialog
    cat=CatalogRepository(tmp_path/'db');repo=ExpensesRepository(cat.connection)
    dialog=ExpenseDialog(repo,SettingsRepository(cat.connection));qtbot.addWidget(dialog);dialog.show();dialog.activateWindow();qtbot.wait(10)
    dialog.concept.setText('Meta');dialog.category.setCurrentIndex(1);dialog.pending.setChecked(True)
    dialog.persist()
    assert dialog.amount.property('invalid') and dialog.amount.hasFocus()
    assert not dialog.concept.property('invalid') and not dialog.account.property('invalid')
    assert not repo.list_movements()
    dialog.amount.setText('42500');dialog.persist()
    assert repo.list_movements()[0]['amount_cents']==4250000
    cat.close()


import pytest

@pytest.mark.parametrize('kind',['category','carrier','account','method','option','loan','purchase','cost','line','reason'])
def test_empty_forms_focus_required_input(qtbot,tmp_path,kind):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.settings_repository import SettingsRepository
    from mi_negocio.expenses_repository import ExpensesRepository
    from mi_negocio.loans_repository import LoansRepository
    from mi_negocio.purchases_repository import PurchasesRepository
    from mi_negocio.ui.expense_categories import ExpenseCategoriesEditor
    from mi_negocio.ui.carriers_editor import CarriersEditor
    from mi_negocio.ui.settings_page import SettingsEditor
    from mi_negocio.ui.options_dialog import OptionsDialog
    from mi_negocio.ui.loans_page import LoanDialog
    from mi_negocio.ui.purchase_dialog import PurchaseDialog
    from mi_negocio.ui.purchase_cost_editor import CostDialog
    from mi_negocio.ui.purchase_line_editor import PurchaseLineDialog
    from mi_negocio.ui.form_validation import RequiredReasonDialog
    cat=CatalogRepository(tmp_path/'db');settings=SettingsRepository(cat.connection)
    if kind=='category':dialog=ExpenseCategoriesEditor(ExpensesRepository(cat.connection));field=dialog.name;save=dialog.persist
    elif kind=='carrier':dialog=CarriersEditor(settings);field=dialog.name;save=dialog.persist
    elif kind in ('account','method'):dialog=SettingsEditor(settings,methods=kind=='method');dialog.clear();field=dialog.name;save=dialog.persist
    elif kind=='option':dialog=OptionsDialog(cat);field=dialog.name;save=dialog.add
    elif kind=='loan':dialog=LoanDialog(LoansRepository(cat.connection));field=dialog.name;save=dialog.persist
    elif kind=='purchase':dialog=PurchaseDialog(cat,PurchasesRepository(cat.connection));field=dialog.supplier;save=dialog.save
    elif kind=='cost':dialog=CostDialog();field=dialog.amount;save=dialog.apply
    elif kind=='line':dialog=PurchaseLineDialog([]);field=dialog.product;save=dialog.accept_line
    else:dialog=RequiredReasonDialog();field=dialog.field;save=dialog.accept
    qtbot.addWidget(dialog);dialog.show();dialog.activateWindow();qtbot.wait(10)
    if kind in ("category","carrier"):dialog.clear()
    save()
    assert field.property('invalid'),kind
    assert field.hasFocus() or (isinstance(field,QComboBox) and field.lineEdit().hasFocus()),kind
    assert dialog.error.text(),kind
    cat.close()


def test_currency_marks_rate_and_allows_optional_reference(qtbot):
    from mi_negocio.ui.purchase_cost_editor import CostDialog
    dialog=CostDialog();qtbot.addWidget(dialog);dialog.show();dialog.activateWindow();qtbot.wait(10)
    dialog.amount.setText('100');dialog.exchange.currency.setCurrentText('USD');dialog.apply()
    assert dialog.exchange.rate.property('invalid') and dialog.exchange.rate.hasFocus()
    dialog.exchange.currency.setCurrentText('COP');dialog.apply()
    assert dialog.result_cost.amount_cents==10000


def test_required_reason_stays_open_until_complete(qtbot):
    from mi_negocio.ui.form_validation import RequiredReasonDialog
    dialog=RequiredReasonDialog();qtbot.addWidget(dialog);dialog.show();dialog.accept()
    assert dialog.isVisible() and dialog.field.property('invalid')
    dialog.field.setText('Registro duplicado');dialog.accept()
    assert dialog.result()==QDialog.Accepted


def test_repository_rejection_remains_visible(qtbot,tmp_path,monkeypatch):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.expenses_repository import ExpensesRepository
    from mi_negocio.ui.expense_categories import ExpenseCategoriesEditor
    from mi_negocio.storage import StorageError
    cat=CatalogRepository(tmp_path/'db');repo=ExpensesRepository(cat.connection)
    dialog=ExpenseCategoriesEditor(repo);qtbot.addWidget(dialog);dialog.show()
    dialog.clear();dialog.name.setText(repo.categories()[0]['name']);dialog.persist()
    assert 'Ya existe' in dialog.error.text() and dialog.error.isVisible()
    assert not dialog.name.property('invalid')
    def reject(*args):raise StorageError('No se pudo guardar el registro.')
    monkeypatch.setattr(repo,'save_category',reject)
    dialog.name.setText('Nueva categoría');dialog.persist()
    assert dialog.error.isVisible() and 'No se pudo' in dialog.error.text()
    cat.close()


def test_sale_required_identification_revealed_and_shipping_focused(qtbot,tmp_path):
    from PySide6.QtCore import QSettings
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.settings_repository import SettingsRepository
    from mi_negocio.sales_repository import SalesRepository
    from mi_negocio.ui.sale_dialog import SaleDialog
    from mi_negocio.ui.preferences import DisplayPreferences
    cat=CatalogRepository(tmp_path/'db');cat.create(validate_product(ProductInput('1','Servicio','service','100')))
    prefs=DisplayPreferences(QSettings(str(tmp_path/'prefs.ini'),QSettings.IniFormat));prefs.set_require_sale_identification(True)
    dialog=SaleDialog(cat,SettingsRepository(cat.connection),SalesRepository(cat.connection),preferences=prefs)
    qtbot.addWidget(dialog);dialog.show();dialog.activateWindow();qtbot.wait(10)
    dialog.customer.setText('Cliente');dialog.customer_more.setChecked(False);dialog.persist()
    assert dialog.customer_identification.property('invalid') and dialog.customer_identification.hasFocus()
    assert dialog.customer_details.isVisible() and dialog.saved_id is None
    dialog.customer_identification.setText('123');dialog.product.setCurrentIndex(1);dialog.append_line();dialog.method_buttons[1].click()
    dialog.shipping.setChecked(True);dialog.shipping_cost.setText('incorrecto');dialog.delivery_toggle.setChecked(False)
    dialog.persist()
    assert dialog.shipping_cost.property('invalid') and dialog.shipping_cost.hasFocus()
    assert dialog.delivery_body.isVisible() and dialog.saved_id is None
    cat.close()
