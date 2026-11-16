from datetime import date
from mi_negocio.sales_analytics import summarize_sales, comparison_dates, evolution


def row(key, total, received=False, cancelled=False, **kw):
    return dict(id=key,total_cents=total,received=received,cancelled_at='x' if cancelled else None,
                commission_cents=100,actual_commission_cents=50 if received else 100,
                shipping_cost_cents=200,shipping_charged_cents=150,sold_on='2026-10-12',**kw)


def test_totals_ranking_and_cancellations():
    rows=[row(1,1000,True),row(2,2001),row(3,9000,cancelled=True)]
    lines=[dict(sale_id=s,product_id=p,code=str(p),name=n,kind=k,quantity=q,unit_price_cents=v)
           for s,p,n,k,q,v in [(1,1,'Máquina','product',2,300),(1,2,'Servicio','service',1,250),
                               (2,1,'Máquina nueva','product',1,1851),(3,3,'Anulada','product',99,10)]]
    result=summarize_sales(rows,lines,[row(4,1500)])
    assert (result['total'],result['count'],result['average'],result['received'],result['pending'])==(3001,2,1501,1000,2001)
    assert result['commissions']==150 and result['estimated_count']==1
    assert result['shipping_cost']==400 and result['shipping_charged']==300
    assert result['products'][0]['units']==3 and result['products'][0]['value']==2451
    assert len(result['products'])==1 and result['services'][0]['value']==250
    assert result['change_percent']>100
    assert summarize_sales([],[],[])['change_percent'] is None


def test_equivalent_periods_and_no_unbounded_comparison():
    today=date(2026,10,24)
    assert comparison_dates(date(2026,10,1),date(2026,10,31),today,True)==(date(2026,9,1),date(2026,9,24))
    assert comparison_dates(date(2024,3,1),date(2024,3,31),today,True)==(date(2024,2,1),date(2024,2,29))
    assert comparison_dates(date(2026,1,1),date(2026,1,10),today,True)==(date(2025,12,1),date(2025,12,10))
    assert comparison_dates(date(2026,10,10),date(2026,10,19),today,False)==(date(2026,9,30),date(2026,10,9))
    assert comparison_dates(None,None,today,False) is None


def test_evolution_includes_empty_buckets_and_totals():
    rows=[row(1,1000),dict(row(2,2000),sold_on='2026-08-01'),row(3,9000,cancelled=True)]
    buckets=evolution(rows,date(2026,8,1),date(2026,10,24),'month')
    assert [b['value'] for b in buckets]==[2000,0,1000]
    assert sum(b['value'] for b in evolution(rows,date(2026,8,1),date(2026,10,24),'week'))==3000


def test_repository_actual_commission_and_historical_lines(tmp_path):
    from mi_negocio.repository import CatalogRepository
    from mi_negocio.catalog import ProductInput,validate_product
    from mi_negocio.settings_repository import SettingsRepository
    from mi_negocio.sales_repository import SalesRepository
    from mi_negocio.sales import SaleDraft,SaleLineInput,ReceiptInput
    cat=CatalogRepository(tmp_path/'db');repo=SalesRepository(cat.connection);settings=SettingsRepository(cat.connection)
    p=cat.create(validate_product(ProductInput('M1','Máquina original','product','1000')))
    service=cat.create(validate_product(ProductInput('S1','Servicio','service','50')))
    method=settings.list_methods()[2]
    draft=SaleDraft(date.today(),'F1',(SaleLineInput(p.id,2,100000),SaleLineInput(service.id,1,5000)),method.id,2,True,2000,3000,customer_name='Cliente')
    sale=repo.create(draft,request_id='first',expected_method=method,receipt=ReceiptInput(date.today(),2,4000))
    rows=repo.list_sales();assert rows[0]['actual_commission_cents']==4000
    assert rows[0]['commission_cents']!=4000
    lines=repo.list_lines([sale['id'],sale['id']]);assert len(lines)==2
    assert {line['kind'] for line in lines}=={'service','product'}
    result=summarize_sales(rows,lines,[])
    assert result['total']==207000 and result['commissions']==4000 and result['shipping_cost']==3000
    assert result['products'][0]['value']==200000 and result['services'][0]['value']==5000
    repo.cancel(sale['id']);assert summarize_sales(repo.list_sales(),lines,[])['count']==0
    assert repo.list_lines([])==[]
    cat.close()


def test_comparison_buckets_align_elapsed_spans_across_months():
    from mi_negocio.sales_analytics import comparative_evolution
    current=evolution([dict(row(1,1000),sold_on='2026-10-12')],date(2026,10,10),date(2026,10,19),'month')
    prior=[dict(row(2,300),sold_on='2026-09-30'),dict(row(3,700),sold_on='2026-10-05')]
    result=comparative_evolution(prior,current,date(2026,9,30),date(2026,10,9))
    assert len(result)==1 and result[0]['value']==1000
    assert (result[0]['start'],result[0]['end'])==(date(2026,9,30),date(2026,10,9))
    current=evolution([],date(2026,3,1),date(2026,3,31),'week')
    prior=[dict(row(4,500),sold_on='2026-02-28')]
    result=comparative_evolution(prior,current,date(2026,2,1),date(2026,2,28))
    assert len(result)==len(current) and sum(r['value'] for r in result)==500
    assert result[-1]['empty'] and result[-1]['value']==0
    current=evolution([],date(2026,2,1),date(2026,2,28),'week')
    result=comparative_evolution([dict(row(5,800),sold_on='2026-01-31')],current,date(2026,1,1),date(2026,1,31))
    assert result[-1]['end']==date(2026,1,31) and sum(r['value'] for r in result)==800


def test_week_label_identifies_both_months():
    result=evolution([],date(2026,9,29),date(2026,10,5),'week')
    assert result[0]['label']=='29 Sep–5 Oct'
