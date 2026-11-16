"""Read-only sales indicators; monetary arithmetic stays in integer cents."""
from datetime import date, timedelta
from decimal import Decimal
from calendar import monthrange
from .expenses import comparison_period

MONTHS=('Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic')


def comparison_dates(start, end, today, monthly=False):
    if start is None or end is None or start>min(end,today):return None
    end=min(end,today)
    if start==date.min:return None
    if not monthly and start.toordinal()<=(end-start).days+1:return None
    return comparison_period(start,end,monthly)


def summarize_sales(rows, lines, previous_rows):
    active={r['id']:r for r in rows if not r['cancelled_at']}
    total=sum(r['total_cents'] for r in active.values());count=len(active)
    received=sum(r['total_cents'] for r in active.values() if r['received'])
    prior=sum(r['total_cents'] for r in previous_rows if not r['cancelled_at'])
    products={};services={}
    for line in lines:
        if line['sale_id'] not in active:continue
        group=products if line['kind']=='product' else services
        key=line['product_id']
        item=group.setdefault(key,dict(id=key,code=line['code'],name=line['name'],units=0,value=0))
        item['units']+=line['quantity'];item['value']+=line.get('line_total_cents',line['quantity']*line['unit_price_cents'])
    return dict(total=total,count=count,average=(2*total+count)//(2*count) if count else 0,
                received=received,pending=total-received,pending_count=sum(not r['received'] for r in active.values()),
                commissions=sum(r['actual_commission_cents'] for r in active.values()),
                estimated_count=sum(not r['received'] and r['commission_cents']>0 for r in active.values()),
                shipping_cost=sum(r['shipping_cost_cents'] for r in active.values()),
                shipping_charged=sum(r['shipping_charged_cents'] for r in active.values()),
                previous_total=prior,change_percent=(Decimal(total-prior)*100/Decimal(prior)) if prior else None,
                products=list(products.values()),services=list(services.values()))


def evolution(rows,start,end,mode='month'):
    active=[r for r in rows if not r['cancelled_at']]
    if start is None:start=min((date.fromisoformat(r['sold_on']) for r in active),default=date.today()).replace(day=1)
    if end is None:end=max((date.fromisoformat(r['sold_on']) for r in active),default=start)
    if start>end:return []
    # Long histories are grouped by year to keep the chart legible and bounded.
    if (end-start).days>730:mode='year'
    result=[];cursor=start
    while cursor<=end:
        if mode=='week':last=min(end,cursor+timedelta(days=min(6,(date.max-cursor).days)))
        elif mode=='year':last=min(end,date(cursor.year,12,31))
        else:last=min(end,date(cursor.year,cursor.month,monthrange(cursor.year,cursor.month)[1]))
        label=(f'{cursor.day}–{last.day} {MONTHS[last.month-1]}' if mode=='week' else str(cursor.year) if mode=='year' else f'{MONTHS[cursor.month-1]} {cursor.year}')
        if mode=='week' and cursor.month!=last.month:label=f'{cursor.day} {MONTHS[cursor.month-1]}–{last.day} {MONTHS[last.month-1]}'
        result.append(dict(start=cursor,end=last,label=label,value=0))
        if last==end:break
        cursor=last+timedelta(days=1)
    # Dates are already sorted in repository output, but aggregation doesn't rely on order.
    for row in active:
        sold=date.fromisoformat(row['sold_on'])
        for bucket in result:
            if bucket['start']<=sold<=bucket['end']:
                bucket['value']+=row['total_cents'];break
    return result


def comparative_evolution(rows, current_buckets, start, end):
    """Align the prior period by elapsed offsets, not unrelated month boundaries.

    Calendar-month comparisons can differ by a few days: the final comparable
    bucket includes the prior month's remaining days; absent spans stay empty.
    """
    result=[];offset=0
    for i,current in enumerate(current_buckets):
        length=(current['end']-current['start']).days+1
        first=start+timedelta(days=offset)
        last=end if i==len(current_buckets)-1 else min(end,first+timedelta(days=length-1))
        empty=first>end
        value=sum(r['total_cents'] for r in rows if not r['cancelled_at'] and first.isoformat()<=r['sold_on']<=last.isoformat()) if not empty else 0
        result.append(dict(start=first,end=last,label=current['label'],value=value,empty=empty))
        offset+=length
    return result
