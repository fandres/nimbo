"""Reglas de gastos y períodos, sin dependencias gráficas."""
from dataclasses import dataclass
from datetime import date, timedelta
from calendar import monthrange
from .catalog import ValidationError
from .sales import check_cents


@dataclass(frozen=True)
class ExpenseDraft:
    concept: str
    amount_cents: int
    spent_on: date
    category_id: int
    paid_on: date | None = None
    account_id: int | None = None
    due_on: date | None = None
    note: str = ''
    voucher: str = ''


@dataclass(frozen=True)
class ExpenseFilter:
    start: date | None = None
    end: date | None = None
    account_id: int | None = None
    category_key: str | None = None
    paid: bool | None = None
    query: str = ''
    cancelled: bool | None = False
    method_id: int | None = None
    date_basis: str = 'spent'


def valid_day(value, title, future=False):
    if type(value) is not date or (not future and value > date.today()):
        raise ValidationError({'fecha': title + ': selecciona una fecha válida' + ('.' if future else ', no futura.')})


def validate_expense(draft):
    check_cents(draft.amount_cents)
    if not draft.concept.strip() or not draft.amount_cents or not draft.category_id:
        raise ValidationError({'gasto': 'Completa concepto, categoría e importe mayor que cero.'})
    valid_day(draft.spent_on,'Fecha del gasto')
    if draft.paid_on is not None:
        valid_day(draft.paid_on,'Fecha de pago')
        if not draft.account_id or draft.paid_on < draft.spent_on:
            raise ValidationError({'pago': 'Selecciona una cuenta y una fecha de pago igual o posterior al gasto.'})
    elif draft.account_id is not None:
        raise ValidationError({'pago': 'Un gasto pendiente no tiene cuenta de pago todavía.'})
    if draft.due_on is not None:
        valid_day(draft.due_on,'Fecha estimada',future=True)
        if draft.due_on < draft.spent_on:
            raise ValidationError({'fecha': 'La fecha estimada no puede ser anterior al gasto.'})


def comparison_period(start, end, monthly=False):
    if start > end:raise ValidationError({'fecha':'La fecha inicial debe ser anterior o igual a la final.'})
    if monthly:
        year,month=(start.year-1,12) if start.month==1 else (start.year,start.month-1)
        previous_last=monthrange(year,month)[1]
        full=end.day==monthrange(end.year,end.month)[1]
        return date(year,month,1),date(year,month,previous_last if full else min(end.day,previous_last))
    return start-timedelta(days=(end-start).days+1),start-timedelta(days=1)
