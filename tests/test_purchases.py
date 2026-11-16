from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import pytest
from mi_negocio.catalog import ValidationError
from mi_negocio.purchases import (PurchaseDraft, PurchaseLineInput, PurchaseCostInput,
    calculate_purchase_totals, convert_to_cop, validate_purchase)


def draft():
    return PurchaseDraft(date.today(), 'Proveedor', '', (
        PurchaseLineInput(1, 2, 30000, 'USD', Decimal('4200'), date.today()),), (
        PurchaseCostInput('international_shipping', '', 5000, 'USD', Decimal('4250'), date.today()),
        PurchaseCostInput('taxes', '', 40000000),))


def test_mixed_currency_costs():
    totals = calculate_purchase_totals(draft())
    assert (totals.merchandise_cents, totals.shipping_import_cents,
            totals.taxes_other_cents, totals.total_cents) == (252000000, 21250000, 40000000, 313250000)


def test_round_once_per_line_and_cop_reference():
    d = replace(draft(), lines=(PurchaseLineInput(1, 3, 1, 'USD', Decimal('1.5'), date.today()),), costs=())
    assert calculate_purchase_totals(d).total_cents == 5
    assert convert_to_cop(40000000, 'COP', Decimal('4200')) == 40000000


@pytest.mark.parametrize('rate', [Decimal('0'), Decimal('-1'), Decimal('NaN'), Decimal('Infinity'), Decimal('1.0000001'), None])
def test_invalid_exchange_rates(rate):
    d = draft()
    with pytest.raises(ValidationError):
        calculate_purchase_totals(replace(d, lines=(replace(d.lines[0], exchange_rate=rate),)))


@pytest.mark.parametrize('quantity', [0, -1, True, 1.5, 2**63])
def test_invalid_quantities(quantity):
    d = draft()
    with pytest.raises(ValidationError):
        calculate_purchase_totals(replace(d, lines=(replace(d.lines[0], quantity=quantity),)))


def test_required_fields_dates_and_overflow():
    d = draft()
    for bad in (replace(d, supplier=' '), replace(d, lines=()),
                replace(d, purchased_on=date.today()+timedelta(days=1)),
                replace(d, lines=(replace(d.lines[0], converted_on=None),)),
                replace(d, costs=(PurchaseCostInput('other', '', 0),)),
                replace(d, lines=(PurchaseLineInput(1, 2, 2**63-1),))):
        with pytest.raises(ValidationError): calculate_purchase_totals(bad)


def test_zero_and_repeated_products_are_explicitly_valid():
    d = replace(draft(), lines=(PurchaseLineInput(1, 1, 0), PurchaseLineInput(1, 1, 0)), costs=())
    validate_purchase(d)
    assert calculate_purchase_totals(d).total_cents == 0
    assert not d.costs_complete


def test_conversion_date_and_optional_reference_pair():
    d = replace(draft(), purchased_on=date.today()-timedelta(days=5))
    validate_purchase(d)
    for cost in (PurchaseCostInput('taxes', '', 100, exchange_rate=Decimal('4200')),
                 PurchaseCostInput('taxes', '', 100, converted_on=date.today()),
                 PurchaseCostInput('taxes', '', 100, 'USD', Decimal('1'), date.today()-timedelta(days=6))):
        with pytest.raises(ValidationError): validate_purchase(replace(d, costs=(cost,)))
