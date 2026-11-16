"""Desglose de IVA configurable; no determina obligaciones tributarias."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
from .catalog import ValidationError


def split_vat(amount, enabled=False, rate=Decimal('19'), included=False):
    from .sales import check_cents
    check_cents(amount)
    if type(enabled) is not bool or type(included) is not bool:
        raise ValidationError({'iva':'Revisa las opciones de IVA.'})
    if not isinstance(rate,Decimal) or not rate.is_finite() or not 0 <= rate <= 100 or rate.as_tuple().exponent < -6:
        raise ValidationError({'iva':'El IVA debe estar entre 0 y 100 %, con hasta seis decimales.'})
    if not enabled:return amount,0,amount
    with localcontext() as context:
        context.prec=60
        if included:
            base=int((Decimal(amount)*100/(100+rate)).quantize(Decimal(1),rounding=ROUND_HALF_UP))
            return base,amount-base,amount
        tax=int((Decimal(amount)*rate/100).quantize(Decimal(1),rounding=ROUND_HALF_UP))
        check_cents(amount+tax)
        return amount,tax,amount+tax


def sale_line_amounts(lines, enabled=False, rate=Decimal('19'), included=False):
    """Reparte el total final por acumulados; la suma conserva todos los centavos."""
    amounts=[line.quantity*line.unit_price_cents for line in lines]
    total=sum(amounts);gross=split_vat(total,enabled,rate,included)[2]
    if not total:return [0]*len(amounts)
    result=[];cumulative=previous=0
    for amount in amounts:
        cumulative+=amount
        rounded=(2*gross*cumulative+total)//(2*total)
        result.append(rounded-previous);previous=rounded
    return result


def migrate_vat(c):
    for table in ('sales','purchase_lines'):
        columns={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
        for name,definition in [('vat_enabled','INTEGER NOT NULL DEFAULT 0'),('vat_rate',"TEXT NOT NULL DEFAULT '19'"),('vat_included','INTEGER NOT NULL DEFAULT 0'),('vat_cents','INTEGER NOT NULL DEFAULT 0')]:
            if name not in columns:c.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    if 'base_cents' not in {r[1] for r in c.execute('PRAGMA table_info(sales)')}:
        c.execute('ALTER TABLE sales ADD COLUMN base_cents INTEGER NOT NULL DEFAULT 0')
        c.execute('UPDATE sales SET base_cents=subtotal_cents')
    if 'line_total_cents' not in {r[1] for r in c.execute('PRAGMA table_info(sale_lines)')}:
        c.execute('ALTER TABLE sale_lines ADD COLUMN line_total_cents INTEGER NOT NULL DEFAULT 0')
        c.execute('UPDATE sale_lines SET line_total_cents=quantity*unit_price_cents')
    c.execute('PRAGMA user_version=21')
