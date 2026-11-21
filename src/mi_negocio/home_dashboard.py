"""Indicadores de Inicio, con el mismo alcance que los módulos de origen."""
from calendar import monthrange
from datetime import date
from decimal import Decimal,ROUND_HALF_UP
from .sales import SalesFilter
from .expenses import ExpenseFilter
from .expenses_repository import ExpensesRepository
from .money_repository import MoneyRepository
from .credit_cards import CreditCardsRepository
from .storage import operation


def month_start(today,offset=0):
    year,month=divmod(today.year*12+today.month-1+offset,12)
    return date(year,month+1,1)


def comparison_range(today):
    start=month_start(today,-1)
    return start,start.replace(day=min(today.day,monthrange(start.year,start.month)[1]))


def percentage_change(current,previous):
    if not previous:return Decimal(0) if not current else None
    return (Decimal(current-previous)*100/previous).quantize(Decimal('.1'),rounding=ROUND_HALF_UP)


def home_snapshot(catalog,sales,today=None):
    today=today or date.today();start=today.replace(day=1);prior_start,prior_end=comparison_range(today)
    with operation(catalog.connection):
        rows=sales.list_sales(SalesFilter(end=today)) if sales else []
        current=[r for r in rows if r['sold_on']>=str(start)]
        previous=[r for r in rows if str(prior_start)<=r['sold_on']<=str(prior_end)]
        pending=sorted((r for r in rows if not r['received']),key=lambda r:(r['sold_on'],r['id']))
        expenses=ExpensesRepository(catalog.connection)
        expense_rows=expenses.list_movements(ExpenseFilter(start,today))
        previous_expenses=expenses.list_movements(ExpenseFilter(prior_start,prior_end))
        unpaid=expenses.list_movements(ExpenseFilter(end=today,paid=False))
        money=MoneyRepository(catalog.connection).summary(start,today)
        products=catalog.list_products(active=True)
        months=[]
        for offset in range(-5,1):
            first=month_start(today,offset);last=min(today,first.replace(day=monthrange(first.year,first.month)[1]))
            months.append(dict(start=first,end=last,value=sum(r['total_cents'] for r in rows if str(first)<=r['sold_on']<=str(last))))
        return dict(today=today,start=start,previous_start=prior_start,previous_end=prior_end,
            sales_total=sum(r['total_cents'] for r in current),sales_count=len(current),sales_previous=sum(r['total_cents'] for r in previous),
            expenses_total=sum(r['amount_cents'] for r in expense_rows),expenses_previous=sum(r['amount_cents'] for r in previous_expenses),expenses_estimated=any(r['estimated'] for r in expense_rows+previous_expenses),
            pending_total=sum(r['total_cents'] for r in pending),pending=pending,unpaid=unpaid,
            unpaid_total=sum(r['amount_cents'] for r in unpaid),next_due=min((r['due_on'] for r in unpaid if r['due_on']),default=None),
            money=money,months=months,recent=rows[:3],products=sum(p.kind=='product' for p in products),services=sum(p.kind=='service' for p in products),
            reminders=CreditCardsRepository(catalog.connection).reminders())
