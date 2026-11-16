"""Reconstruct valuation using existing inventory events; never writes or commits."""
from collections import defaultdict
import json
from .fifo import FifoLedger, Lot
from .purchase_allocation import ALLOCATION_FIELDS, purchase_progress
from .purchases_repository import PurchasesRepository, draft_from_record


def reconstruct_fifo(connection):
    ledger = FifoLedger()
    state = connection.execute('SELECT * FROM inventory_state WHERE id=1').fetchone()
    receipts = {r['id']: dict(r) for r in connection.execute('SELECT * FROM purchase_receipts')}
    lines = defaultdict(list)
    for row in connection.execute('SELECT * FROM receipt_lines ORDER BY id'):
        lines[row['receipt_id']].append(dict(row))
    purchase_lines = {r['id']: dict(r) for r in connection.execute('SELECT * FROM purchase_lines')}
    progress = {}
    repo = PurchasesRepository(connection)
    for row in connection.execute('SELECT id FROM purchases'):
        record = repo._get(row['id'])
        progress[row['id']] = purchase_progress(draft_from_record(record), bool(record['cancelled_at']))['state']

    def add_receipt(receipt_id, product_id):
        receipt = receipts.get(receipt_id)
        added = 0
        for line in lines[receipt_id]:
            if line['product_id'] != product_id:
                continue
            source = purchase_lines.get(line['purchase_line_id'])
            reason, total, provisional = '', None, False
            if (not receipt or not source or source['quantity'] != line['quantity']
                    or source['product_id'] != product_id or source['purchase_id'] != receipt['purchase_id']):
                reason = 'Línea de compra de origen no coincide con la recepción'
            elif receipt['reversed_at']:
                reason = 'Recepción de origen revertida'
            elif progress.get(receipt['purchase_id']) == 'cancelled':
                reason = 'Compra de origen anulada'
            else:
                total = source['subtotal_cents'] + source['vat_cents']
                total += sum(source[field] for field in ALLOCATION_FIELDS.values())
                total += sum(json.loads(source['extra_allocations_json'] or '{}').values())
                provisional = progress.get(receipt['purchase_id']) != 'complete'
                if provisional:
                    reason = 'Compra con costos pendientes o gastos sin distribuir'
            ledger.add(Lot(('receipt', line['id']), product_id, line['quantity'], total,
                           (receipt['received_on'] if receipt else '', receipt_id, line['id']),
                           purchase_id=receipt['purchase_id'] if receipt else None,
                           receipt_id=receipt_id, reason=reason, provisional=provisional))
            added += line['quantity']
        return added

    baseline = [r[0] for r in connection.execute('SELECT receipt_id FROM inventory_baseline_receipts ORDER BY receipt_id')]
    for event in connection.execute('SELECT * FROM inventory_movements ORDER BY id'):
        product, delta, kind = event['product_id'], event['delta'], event['kind']
        parts = event['operation_key'].split(':')
        if kind == 'opening':
            added = sum(add_receipt(key, product) for key in baseline) if state['mode'] == 'receipts' else 0
            if delta > added:
                ledger.add(Lot(('opening', event['id']), product, delta-added, None,
                               (event['created_at'][:10], 0, event['id']), reason='Existencias iniciales sin costo trazable'))
            elif added > delta:
                ledger.consume(product, added-delta)
        elif kind == 'receipt':
            added = add_receipt(int(parts[1]), product)
            if added < delta:
                ledger.add(Lot(('missing-receipt', event['id']), product, delta-added, None,
                               (event['created_at'][:10], 0, event['id']), reason='Recepción sin detalle trazable'))
        elif kind in ('sale', 'cancellation'):
            sale_id = int(parts[1])
            if delta < 0:
                ledger.consume(product, -delta, sale_id=sale_id)
            elif delta > 0:
                ledger.restore(sale_id, product, delta)
        elif kind == 'reversal':
            ledger.reverse(int(parts[1]), product, -delta)
        elif delta < 0:
            ledger.consume(product, -delta)
        elif delta > 0:
            ledger.add(Lot(('adjustment', event['id']), product, delta, None,
                           (event['created_at'][:10], 0, event['id']), reason='Ajuste positivo sin costo de compra'))
    return ledger


def receipt_has_sales(connection, receipt_id):
    ledger = reconstruct_fifo(connection)
    active = {r[0] for r in connection.execute('SELECT id FROM sales WHERE cancelled_at IS NULL')}
    return any(lot.receipt_id == receipt_id and qty > 0
               for (sale_id, _), tranches in ledger.allocations.items() if sale_id in active
               for lot, _, qty in tranches)
