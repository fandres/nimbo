from datetime import date, timedelta
from decimal import Decimal
from test_inventory_repository import ctx, start, sell, buy
from test_fifo_repository import valued_buy
from mi_negocio.profitability_repository import ProfitabilityRepository
from mi_negocio.sales import SaleDraft, SaleLineInput, ReceiptInput
from mi_negocio.sales_repository import SalesRepository
from mi_negocio.settings_repository import SettingsRepository
from mi_negocio.expenses_repository import ExpensesRepository
from mi_negocio.expenses import ExpenseDraft


def report(cat,query=''):
    return ProfitabilityRepository(cat.connection).report(date.today(),date.today(),query)


def test_profit_vat_commission_shipping_withholding_and_expenses_once(ctx):
    cat,p,s,inv=ctx;start(inv);valued_buy(cat,p,1,5000,'a')
    method=SettingsRepository(cat.connection).list_methods()[0]
    draft=SaleDraft(date.today(),'FE-1',(SaleLineInput(p.id,1,10000),),method.id,1,
        shipping_enabled=True,shipping_charged_cents=1000,shipping_cost_cents=800,
        customer_name='Cliente',customer_email='cliente@example.com',has_withholding=True,
        vat_enabled=True,commission_override=(Decimal('5'),0))
    sale=SalesRepository(cat.connection).create(draft,request_id='sale',expected_method=method,receipt=ReceiptInput(date.today(),1,400))
    expenses=ExpensesRepository(cat.connection)
    expenses.save(ExpenseDraft('Marketing',300,date.today(),expenses.categories()[0]['id']),request_id='expense')
    snapshot=report(cat);row=snapshot['rows'][0]
    assert row['income_cents']==11000
    assert row['cost_cents']==5000 and row['margin_cents']==4800
    assert snapshot['expenses_cents']==300 and snapshot['result_cents']==4500
    assert snapshot['unknown_count']==0 and not snapshot['provisional']
    assert report(cat,'Cliente')['result_cents'] is None  # no arbitrary expense attribution
    SalesRepository(cat.connection).cancel(sale['id'])
    assert report(cat)['result_cents']==-300


def test_service_and_untracked_cost_make_period_incomplete(ctx):
    cat,p,s,inv=ctx;sell(cat,p);sell(cat,s,request='service')
    snapshot=report(cat)
    assert snapshot['unknown_count']==2 and snapshot['result_cents'] is None
    assert all(row['margin_cents'] is None for row in snapshot['rows'])
    assert any('Servicio' in ' '.join(row['reasons']) for row in snapshot['rows'])


def test_pending_cost_is_provisional_and_report_does_not_write(ctx):
    cat,p,s,inv=ctx;start(inv);buy(cat,p);sell(cat,p)
    before=cat.connection.total_changes
    snapshot=report(cat)
    assert snapshot['provisional'] and snapshot['rows'][0]['cost_cents']==100
    assert snapshot['result_cents']==0
    assert before==cat.connection.total_changes
    assert not report(cat,'no coincide')['rows']


def test_period_filters_sales_but_fifo_uses_earlier_movements(ctx):
    cat,p,s,inv=ctx;start(inv);valued_buy(cat,p,2,100,'a')
    first=sell(cat,p);valued_buy(cat,p,2,200,'b');second=sell(cat,p,2,'second')
    with cat.connection:
        cat.connection.execute('UPDATE sales SET sold_on=? WHERE id=?',(str(date.today()-timedelta(days=1)),first['id']))
    snapshot=report(cat)
    assert len(snapshot['rows'])==1 and snapshot['rows'][0]['id']==second['id']
    assert snapshot['rows'][0]['cost_cents']==300
