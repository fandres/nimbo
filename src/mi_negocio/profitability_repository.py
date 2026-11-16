"""Management profitability snapshot, separate from cash flow and tax settlement."""
from collections import defaultdict
from .storage import operation
from .fifo_repository import reconstruct_fifo
from .sales_repository import SalesRepository
from .expenses_repository import ExpensesRepository
from .expenses import ExpenseFilter


class ProfitabilityRepository:
    def __init__(self, connection):
        self.connection = connection

    def report(self, start, end, query=''):
        if start > end:
            raise ValueError('Revisa el rango de fechas.')
        query = query.strip()
        with operation(self.connection):
            ledger = reconstruct_fifo(self.connection)
            sales = SalesRepository(self.connection)
            kinds = {r['id']: r['kind'] for r in self.connection.execute('SELECT id,kind FROM products')}
            rows = []
            for record in self.connection.execute('SELECT id FROM sales WHERE cancelled_at IS NULL AND sold_on BETWEEN ? AND ? ORDER BY sold_on DESC,id DESC', (str(start), str(end))):
                sale = sales._get(record['id'])
                text = ' '.join([sale['customer_name'], sale['customer_alias'], sale['invoice_ref']] +
                                [line['code']+' '+line['name'] for line in sale['lines']])
                if query.casefold() not in text.casefold():
                    continue
                quantities = defaultdict(int)
                for line in sale['lines']:
                    quantities[line['product_id']] += line['quantity']
                known, unknown, provisional = 0, False, False
                reasons, purchases = set(), set()
                for product, quantity in quantities.items():
                    if kinds.get(product) != 'product':
                        unknown = True
                        reasons.add('Servicio sin costo directo registrado')
                        continue
                    value = ledger.value(sale['id'], product)
                    if not sale['stock_tracked'] or value['quantity'] != quantity:
                        unknown = True
                        reasons.add('Venta sin costo trazable para todas sus unidades')
                        continue
                    known += value['known_cents']
                    unknown |= value['cost_cents'] is None
                    provisional |= value['provisional']
                    reasons.update(value['reasons'])
                    purchases.update(value['purchases'])
                commission = sale['receipt']['commission_cents'] if sale['receipt'] else sale['commission_cents']
                estimated = sale['receipt'] is None and commission > 0
                if estimated:
                    reasons.add('Comisión estimada; pendiente de confirmar el cobro')
                income = sale['total_cents'] - sale['vat_cents']
                shipping = sale['shipping_cost_cents'] if sale['shipping_enabled'] else 0
                rows.append(dict(id=sale['id'], sold_on=sale['sold_on'], customer=sale['customer_name'],
                    invoice=sale['invoice_ref'], income_cents=income, cost_cents=None if unknown else known,
                    known_cost_cents=known, commission_cents=commission, shipping_cents=shipping,
                    margin_cents=None if unknown else income-known-commission-shipping,
                    provisional=provisional or estimated, reasons=sorted(reasons), purchases=sorted(purchases)))
            expenses = ExpensesRepository(self.connection)
            movements = expenses._filter(expenses._movements(), ExpenseFilter(start=start, end=end))
            other_expenses = sum(r['amount_cents'] for r in movements if r['origin'] != 'sale')
            unknown_count = sum(row['cost_cents'] is None for row in rows)
            margin = None if unknown_count else sum(row['margin_cents'] for row in rows)
            return dict(rows=rows, income_cents=sum(r['income_cents'] for r in rows),
                        known_cost_cents=sum(r['known_cost_cents'] for r in rows),
                        commission_cents=sum(r['commission_cents'] for r in rows),
                        shipping_cents=sum(r['shipping_cents'] for r in rows), margin_cents=margin,
                        expenses_cents=other_expenses, result_cents=margin-other_expenses if margin is not None and not query else None,
                        unknown_count=unknown_count, provisional=any(r['provisional'] for r in rows), query=query)
