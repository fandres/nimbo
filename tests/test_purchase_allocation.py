from dataclasses import replace
from datetime import date
import pytest
from mi_negocio.catalog import ValidationError
from mi_negocio.purchases import PurchaseDraft, PurchaseLineInput, PurchaseCostInput, validate_purchase
from mi_negocio.purchase_allocation import allocation_summary, line_unit_costs, purchase_progress


def example():
    return PurchaseDraft(date.today(), 'Proveedor', '', (
        PurchaseLineInput(1, 2, 100000000, shipping_allocated_cents=12000000),
        PurchaseLineInput(2, 1, 200000000, shipping_allocated_cents=18000000)),
        (PurchaseCostInput('international_shipping', '', 30000000),), True,
        dict(international_shipping='recorded', importation='not_applicable', taxes='not_applicable', other='not_applicable'))


def test_manual_costs_and_progress():
    d = example()
    validate_purchase(d)
    assert allocation_summary(d)['complete']
    assert line_unit_costs(d.lines[0])['landed_cents'] == 106000000
    assert line_unit_costs(d.lines[1])['landed_cents'] == 218000000
    assert purchase_progress(d)['state'] == 'complete'
    partial = replace(d, lines=(replace(d.lines[0], shipping_allocated_cents=0), d.lines[1]))
    assert purchase_progress(partial)['state'] == 'allocation_pending'
    pending = replace(d, costs_complete=False, cost_states={**d.cost_states, 'taxes':'pending'})
    assert purchase_progress(pending)['pending_categories'] == ['taxes']
    assert purchase_progress(pending, True)['state'] == 'cancelled'


def test_excess_and_inconsistent_states():
    d=example()
    for bad in (replace(d, lines=(replace(d.lines[0], shipping_allocated_cents=40000000),)),
                replace(d, cost_states={**d.cost_states, 'international_shipping':'not_applicable'}),
                replace(d, cost_states={**d.cost_states, 'taxes':'recorded'}),
                replace(d, lines=(replace(d.lines[0], taxes_allocated_cents=-1),))):
        with pytest.raises(ValidationError): validate_purchase(bad)


def test_legacy_and_rounding():
    d=replace(example(),cost_states=None,costs_complete=False)
    assert purchase_progress(d)['legacy']
    assert purchase_progress(d)['pending_categories'] == []
    line=PurchaseLineInput(1,3,0,shipping_allocated_cents=5)
    assert line_unit_costs(line)['approximate']
