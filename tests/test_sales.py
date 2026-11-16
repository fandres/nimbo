from decimal import Decimal
import pytest
from mi_negocio.sales import SaleLineInput, calculate_totals
from mi_negocio.catalog import ValidationError


def test_bolt_shipping():
    t = calculate_totals((SaleLineInput(1, 1, 100000000),), 2000000, 2500000, Decimal('3.59'), 90000)
    assert (t.total_cents,t.commission_cents,t.deposit_cents,t.net_after_shipping_cents)==(102000000,3751800,98248200,95748200)


def test_addi_free_shipping_and_rounding():
    t=calculate_totals((SaleLineInput(1,1,100000000),),0,2500000,Decimal('7.735'),0)
    assert t.commission_cents==7735000
    assert t.net_after_shipping_cents==89765000
    assert calculate_totals((SaleLineInput(1,1,1),),0,0,Decimal('50'),0).commission_cents==1


@pytest.mark.parametrize('lines,rate,fixed',[((),Decimal(0),0),((SaleLineInput(1,0,100),),Decimal(0),0),((SaleLineInput(1,2,2**62),),Decimal(0),0),((SaleLineInput(1,1,1),),Decimal(0),2),((SaleLineInput(1,1,100),),Decimal('NaN'),0)])
def test_invalid(lines,rate,fixed):
    with pytest.raises(ValidationError): calculate_totals(lines,0,0,rate,fixed)


def test_informative_withholding_on_total_with_shipping():
    from mi_negocio.sales import informative_withholding
    assert informative_withholding(102000000)==2550000
    assert informative_withholding(20)==1  # 0.5 cent rounds upward.


def test_colombian_grouped_shipping_amounts():
    from mi_negocio.sales import money
    assert money('42.500')==4250000
    assert money('42.500,50')==4250050
    assert money('42500.50')==4250050
