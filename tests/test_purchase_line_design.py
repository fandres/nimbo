from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from mi_negocio.ui.purchase_line_editor import PurchaseLineDialog
from mi_negocio.purchases import PurchaseLineInput, line_vat_cop, line_original_total, convert_to_cop


def test_design_usd_summary_and_vat_modes(qtbot):
    d=PurchaseLineDialog([SimpleNamespace(id=1,code='10',name='Máquina')]);qtbot.addWidget(d)
    d.product.setCurrentIndex(0);d.quantity.setValue(2);d.amount.setText('850')
    d.exchange.set_values('USD',Decimal('4100'),date.today())
    d.vat.excluded.click()
    assert d.base_summary.text()=='$ 3.485.000,00'
    assert d.vat_summary.text()=='$ 662.150,00'
    assert d.total_summary.text()=='$ 4.147.150,00 COP'
    d.vat.rate_5.click()
    assert d.vat_summary.text()=='$ 174.250,00'
    d.vat.included.click()
    assert d.total_summary.text()=='$ 3.485.000,00 COP'
    d.accept_line()
    line=d.result_line
    assert line.vat_included and line.vat_rate==Decimal('5')
    assert convert_to_cop(line_original_total(line),'USD',Decimal('4100'))+line_vat_cop(line)==348500000
    d.vat.no_vat.click()
    assert not d.vat.values()['vat_enabled']
    assert d.vat_summary.text()=='$ 0,00'


def test_design_blocks_all_vat_choices_and_clears_stale_summary(qtbot):
    d=PurchaseLineDialog([]);qtbot.addWidget(d)
    d.amount.setText('119');d.vat.included.click()
    assert d.base_summary.text()=='$ 100,00'
    d.vat.no_vat.click();d.vat.enabled.setEnabled(False)
    assert not d.vat.excluded.isEnabled() and not d.vat.included.isEnabled()
    d.exchange.set_values('USD',Decimal('4000'),date.today())
    d.exchange.rate.clear()
    assert d.total_summary.text()=='—'
    d.exchange.currency.setCurrentText('COP')
    assert d.total_summary.text()=='$ 119,00 COP'


def test_design_custom_rate_roundtrip_and_quantity_buttons(qtbot):
    line=PurchaseLineInput(1,3,3333,total_cost_cents=10000,vat_enabled=True,vat_rate=Decimal('7.735'))
    d=PurchaseLineDialog([SimpleNamespace(id=1,code='1',name='Máquina')],line);qtbot.addWidget(d)
    assert d.vat.other_rate.isChecked()
    assert d.vat.values()['vat_rate']==Decimal('7.735')
    d.unit_mode.click();d.total_mode.click();assert d.original_total()==10000
    d.increase.click();assert d.quantity.value()==4
    d.quantity.setEnabled(False);d.increase.click();assert d.quantity.value()==4
    assert not d.increase.isEnabled() and not d.decrease.isEnabled()


def test_custom_rate_stays_open_while_typing_standard_prefix(qtbot):
    d=PurchaseLineDialog([]);qtbot.addWidget(d);d.show()
    d.vat.excluded.click();d.vat.other_rate.click()
    d.vat.rate.clear();qtbot.keyClicks(d.vat.rate,'5,5')
    assert d.vat.rate.isVisible()
    assert d.vat.other_rate.isChecked()
    assert d.vat.values()['vat_rate']==Decimal('5.5')


def test_usd_fractional_conversion_summary_matches_saved_line(qtbot):
    d=PurchaseLineDialog([SimpleNamespace(id=1,code='1',name='Máquina')]);qtbot.addWidget(d)
    d.product.setCurrentIndex(0);d.amount.setText('0,03')
    d.exchange.set_values('USD',Decimal('1.5'),date.today());d.vat.excluded.click()
    d.accept_line()
    from mi_negocio.ui.style import format_cop
    assert d.vat_summary.text()==format_cop(line_vat_cop(d.result_line))


def test_quantity_text_and_cost_alignment_remain_visible(qtbot):
    d=PurchaseLineDialog([]);qtbot.addWidget(d);d.resize(820,760);d.show()
    qtbot.waitExposed(d)
    assert d.quantity.lineEdit().width()>40
    before=d.amount.geometry()
    d.unit_mode.click()
    assert d.amount.geometry()==before
    d.vat.enabled.setToolTip('Ya existe IVA en el pedido')
    assert d.vat.excluded.toolTip()=='Ya existe IVA en el pedido'
