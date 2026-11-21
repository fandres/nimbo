"""Pedidos y costos; escritura atómica e historial anterior a cada corrección."""
from .purchases import line_original_total, line_vat_cop, line_base_cop, apply_invoice_vat
from dataclasses import asdict
from datetime import datetime, timezone, date
from decimal import Decimal
import json
from .purchases import definitions_for
from .purchase_concepts import default_definitions
from .purchases import calculate_purchase_totals, convert_to_cop, PurchasesFilter
from .storage import operation, StorageError
from .purchase_receipts_repository import current_receipt
from .purchases import PurchaseDraft, PurchaseLineInput, PurchaseCostInput
from .purchase_allocation import ALLOCATION_FIELDS, purchase_progress, automatic_allocations


def serialized(value):
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)


def now():
    return datetime.now(timezone.utc).isoformat()


class PurchasesRepository:
    def __init__(self, connection):
        self.connection = connection

    def _get(self, purchase_id):
        row = self.connection.execute('SELECT * FROM purchases WHERE id=?', (purchase_id,)).fetchone()
        if row is None:
            raise StorageError('La compra no existe.')
        result = dict(row)
        result.pop('request_payload')
        result['cost_states'] = json.loads(result.pop('cost_states_json')) if result.get('cost_states_json') else None
        result['cost_definitions']=json.loads(result['cost_definitions_json']) if result.get('cost_definitions_json') else default_definitions()
        for name, table in (('lines', 'purchase_lines'), ('costs', 'purchase_costs')):
            result[name] = [dict(r) for r in self.connection.execute(
                f'SELECT * FROM {table} WHERE purchase_id=? ORDER BY id', (purchase_id,))]
        merchandise = sum(line['subtotal_cents'] for line in result['lines'])
        shipping = sum(c['subtotal_cents'] for c in result['costs'] if result['cost_definitions'][c['category']]['group']=='shipping')
        vat=sum(line['vat_cents'] for line in result['lines'])
        other = sum(c['subtotal_cents'] for c in result['costs']) - shipping + vat
        result['totals'] = dict(merchandise_cents=merchandise, shipping_import_cents=shipping,
                               taxes_other_cents=other, vat_cents=vat, total_cents=merchandise+shipping+other)
        result['total_cents'] = merchandise+shipping+other
        result['receipt']=current_receipt(self.connection,purchase_id)
        result['received_quantity']=sum(line['quantity'] for line in result['receipt']['lines']) if result['receipt'] else 0
        result['quantity'] = sum(line['quantity'] for line in result['lines'])
        result['revisions'] = [dict(revision=r['revision'], changed_at=r['changed_at'], snapshot=json.loads(r['snapshot']))
            for r in self.connection.execute('SELECT * FROM purchase_revisions WHERE purchase_id=? ORDER BY revision', (purchase_id,))]
        return result

    def get(self, purchase_id):
        with operation(self.connection):
            return self._get(purchase_id)

    def _write_lines(self, purchase_id, draft, previous=None):
        old = {r['id']: r for r in previous['lines']} if previous else {}
        retained = set()
        for line in draft.lines:
            historical = old.get(line.line_id)
            if line.line_id is not None:
                if not historical or historical['product_id'] != line.product_id or line.line_id in retained:
                    raise StorageError('La línea histórica no corresponde a este producto o compra.')
                retained.add(line.line_id)
                code, name = historical['code'], historical['name']
            else:
                product = self.connection.execute("SELECT * FROM products WHERE id=? AND active=1 AND kind='product'", (line.product_id,)).fetchone()
                if product is None:
                    raise StorageError('Las líneas nuevas requieren un producto físico activo.')
                code, name = product['code'], product['name']
            values = (line.product_id, code, name, line.quantity, line.unit_cost_cents, line.currency,
                      str(line.exchange_rate) if line.exchange_rate is not None else None,
                      line.converted_on.isoformat() if line.converted_on else None,
                      line_base_cop(line))
            if historical:
                self.connection.execute('''UPDATE purchase_lines SET product_id=?,code=?,name=?,quantity=?,unit_cost_cents=?,
                    currency=?,exchange_rate=?,converted_on=?,subtotal_cents=? WHERE id=?''', (*values, line.line_id))
            else:
                cursor = self.connection.execute('''INSERT INTO purchase_lines(product_id,code,name,quantity,unit_cost_cents,
                    currency,exchange_rate,converted_on,subtotal_cents,purchase_id) VALUES(?,?,?,?,?,?,?,?,?,?)''', (*values, purchase_id))
            target_id = line.line_id if historical else cursor.lastrowid
            self.connection.execute('UPDATE purchase_lines SET vat_enabled=?,vat_rate=?,vat_included=?,vat_cents=? WHERE id=?',(int(line.vat_enabled),str(line.vat_rate),int(line.vat_included),line_vat_cop(line),target_id))
            self.connection.execute('UPDATE purchase_lines SET total_cost_cents=? WHERE id=?', (line.total_cost_cents, target_id))
            self.connection.execute('UPDATE purchase_lines SET extra_allocations_json=? WHERE id=?',(serialized(line.extra_allocations),target_id))
            assignments = ','.join(field+'=?' for field in ALLOCATION_FIELDS.values())
            self.connection.execute('UPDATE purchase_lines SET '+assignments+' WHERE id=?',
                (*[getattr(line,field) for field in ALLOCATION_FIELDS.values()], target_id))
        for key in old.keys() - retained:
            self.connection.execute('DELETE FROM purchase_lines WHERE id=?', (key,))
        self.connection.execute('UPDATE purchases SET invoice_vat_enabled=?,invoice_vat_rate=? WHERE id=?',
                                (int(draft.invoice_vat_enabled),str(draft.invoice_vat_rate),purchase_id))
        self.connection.execute('UPDATE purchases SET supplier_alias=?,tracking_number=? WHERE id=?',(draft.supplier_alias.strip(),draft.tracking_number.strip(),purchase_id))
        self.connection.execute('UPDATE purchases SET cost_definitions_json=? WHERE id=?',(serialized(definitions_for(draft)),purchase_id))
        self.connection.execute('UPDATE purchases SET cost_states_json=? WHERE id=?',
            (serialized(draft.cost_states) if draft.cost_states is not None else None, purchase_id))
        self.connection.execute('DELETE FROM purchase_costs WHERE purchase_id=?', (purchase_id,))
        for cost in draft.costs:
            self.connection.execute('''INSERT INTO purchase_costs(purchase_id,category,description,amount_cents,currency,
                exchange_rate,converted_on,subtotal_cents) VALUES(?,?,?,?,?,?,?,?)''',
                (purchase_id, cost.category, cost.description.strip(), cost.amount_cents, cost.currency,
                 str(cost.exchange_rate) if cost.exchange_rate is not None else None,
                 cost.converted_on.isoformat() if cost.converted_on else None,
                 convert_to_cop(cost.amount_cents, cost.currency, cost.exchange_rate)))

    def create(self, draft, *, request_id):
        payload = serialized(asdict(draft))
        if not request_id:
            raise StorageError('Falta el identificador de guardado.')
        with operation(self.connection):
            existing = self.connection.execute('SELECT id,request_payload FROM purchases WHERE request_id=?', (request_id,)).fetchone()
            if existing:
                if normalized_payload(existing['request_payload']) != normalized_payload(payload):
                    raise StorageError('Esta solicitud ya se guardó con otros datos. Abre la compra para corregirla.')
                return self._get(existing['id'])
            draft = automatic_allocations(apply_invoice_vat(draft))
            calculate_purchase_totals(draft)
            timestamp = now()
            cursor = self.connection.execute('''INSERT INTO purchases(request_id,request_payload,purchased_on,supplier,reference,
                costs_complete,revision,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?)''',
                (request_id, payload, draft.purchased_on.isoformat(), draft.supplier.strip(), draft.reference.strip(),
                 int(draft.costs_complete), timestamp, timestamp))
            self._write_lines(cursor.lastrowid, draft)
            return self._get(cursor.lastrowid)

    def _editable(self, purchase_id, expected_revision):
        previous = self._get(purchase_id)
        if previous['cancelled_at']:
            raise StorageError('La compra está anulada y se conserva solo para consulta.')
        if previous['revision'] != expected_revision:
            raise StorageError('La compra cambió desde que la abriste. Conserva tus cambios y recarga antes de guardar.')
        return previous

    def _snapshot(self, previous):
        snapshot = {k: v for k, v in previous.items() if k != 'revisions'}
        self.connection.execute('INSERT INTO purchase_revisions(purchase_id,revision,changed_at,snapshot) VALUES(?,?,?,?)',
                                (previous['id'], previous['revision'], now(), serialized(snapshot)))

    def update(self, purchase_id, draft, *, expected_revision):
        with operation(self.connection):
            previous = self._editable(purchase_id, expected_revision)
            draft = automatic_allocations(apply_invoice_vat(draft))
            calculate_purchase_totals(draft)
            if previous['receipt']:
                expected={line['id']:(line['product_id'],line['quantity']) for line in previous['lines']}
                actual={line.line_id:(line.product_id,line.quantity) for line in draft.lines}
                if len(draft.lines)!=len(expected) or actual!=expected:
                    raise StorageError('La compra ya fue recibida. Deshaz la recepción antes de cambiar modelos o cantidades.')
                if draft.purchased_on.isoformat()>previous['receipt']['received_on']:
                    raise StorageError('La compra no puede ser posterior a su recepción.')
            self._snapshot(previous)
            self._write_lines(purchase_id, draft, previous)
            self.connection.execute('''UPDATE purchases SET purchased_on=?,supplier=?,reference=?,costs_complete=?,
                revision=revision+1,updated_at=? WHERE id=?''',
                (draft.purchased_on.isoformat(), draft.supplier.strip(), draft.reference.strip(), int(draft.costs_complete), now(), purchase_id))
            return self._get(purchase_id)

    def cancel(self, purchase_id, reason, *, expected_revision):
        if not reason.strip():
            raise StorageError('Escribe el motivo de anulación.')
        with operation(self.connection):
            previous = self._editable(purchase_id, expected_revision)
            if previous['receipt']:raise StorageError('Deshaz la recepción antes de anular esta compra.')
            self._snapshot(previous)
            timestamp = now()
            self.connection.execute('''UPDATE purchases SET cancelled_at=?,cancellation_reason=?,updated_at=?,
                revision=revision+1 WHERE id=?''', (timestamp, reason.strip(), timestamp, purchase_id))
            return self._get(purchase_id)

    def list_purchases(self, filters=PurchasesFilter()):
        if filters.start and filters.end and filters.start > filters.end:
            raise StorageError('La fecha inicial debe ser anterior o igual a la final.')
        where, values = [], []
        for column, operator, value in (('p.purchased_on', '>=', filters.start), ('p.purchased_on', '<=', filters.end),
                                         ('p.costs_complete', '=', filters.costs_complete)):
            if value is not None:
                where.append(f'{column}{operator}?')
                values.append(value.isoformat() if hasattr(value, 'isoformat') else int(value))
        if filters.received is not None:
            where.append(('' if filters.received else 'NOT ')+ 'EXISTS(SELECT 1 FROM purchase_receipts r WHERE r.purchase_id=p.id AND r.reversed_at IS NULL)')
        if filters.cancelled is not None:
            where.append('p.cancelled_at IS ' + ('NOT NULL' if filters.cancelled else 'NULL'))
        if filters.query.strip():
            where.append('''(instr(casefold(p.supplier),?)>0 OR instr(casefold(p.supplier_alias),?)>0 OR instr(casefold(p.reference),?)>0 OR EXISTS(
                SELECT 1 FROM purchase_lines l WHERE l.purchase_id=p.id AND
                (instr(casefold(l.code),?)>0 OR instr(casefold(l.name),?)>0)))''')
            values.extend([filters.query.strip().casefold()]*5)
        with operation(self.connection):
            keys = self.connection.execute('SELECT p.id FROM purchases p' + (' WHERE '+' AND '.join(where) if where else '') +
                                           ' ORDER BY p.purchased_on DESC,p.id DESC', values).fetchall()
            rows = [self._get(r['id']) for r in keys]
            return [row for row in rows if matches_progress(row, filters.progress)]

    def supplier_suggestions(self):
        with operation(self.connection):
            rows=self.connection.execute('SELECT supplier,supplier_alias FROM purchases ORDER BY id DESC')
            unique={}
            for row in rows:
                name,alias=row['supplier'].strip(),row['supplier_alias'].strip()
                unique.setdefault((name.casefold(),alias.casefold()),(name,alias))
            return sorted(unique.values(),key=lambda pair:(pair[1] or pair[0]).casefold())

    def list_suppliers(self):
        with operation(self.connection):
            rows = self.connection.execute('SELECT supplier FROM purchases ORDER BY id')
            unique = {}
            for row in rows:
                unique.setdefault(row[0].strip().casefold(), row[0].strip())
            return sorted(unique.values(), key=str.casefold)


def normalized_payload(payload):
    value=json.loads(payload)
    value.setdefault('cost_states',None)
    value.setdefault('cost_definitions',None)
    value.setdefault('supplier_alias','')
    value.setdefault('tracking_number','')
    value.setdefault('invoice_vat_enabled',False)
    value.setdefault('invoice_vat_rate','19')
    for line in value['lines']:
        line.pop('invoice_vat_share_cents',None)
        line.setdefault('vat_enabled',False);line.setdefault('vat_rate','19');line.setdefault('vat_included',False)
        line.setdefault('total_cost_cents',None)
        line.setdefault('extra_allocations',{})
        for field in ALLOCATION_FIELDS.values(): line.setdefault(field,0)
    return value


def draft_from_record(row):
    lines=tuple(PurchaseLineInput(r['product_id'],r['quantity'],r['unit_cost_cents'],r['currency'],
        Decimal(r['exchange_rate']) if r['exchange_rate'] is not None else None,
        date.fromisoformat(r['converted_on']) if r['converted_on'] else None,r['id'],
        invoice_vat_share_cents=r.get('vat_cents',0) if row.get('invoice_vat_enabled') else None,
        vat_enabled=bool(r.get('vat_enabled',False)),vat_rate=Decimal(r.get('vat_rate','19')),vat_included=bool(r.get('vat_included',False)),total_cost_cents=r.get('total_cost_cents'), extra_allocations=json.loads(r.get('extra_allocations_json') or '{}'), **{field:r.get(field,0) for field in ALLOCATION_FIELDS.values()}) for r in row['lines'])
    costs=tuple(PurchaseCostInput(r['category'],r['description'],r['amount_cents'],r['currency'],
        Decimal(r['exchange_rate']) if r['exchange_rate'] is not None else None,
        date.fromisoformat(r['converted_on']) if r['converted_on'] else None) for r in row['costs'])
    return PurchaseDraft(date.fromisoformat(row['purchased_on']),row['supplier'],row['reference'],lines,costs,
                         bool(row['costs_complete']),row.get('cost_states'),row.get('cost_definitions',default_definitions()),row.get('supplier_alias',''),row.get('tracking_number',''),
                         bool(row.get('invoice_vat_enabled',False)),Decimal(row.get('invoice_vat_rate','19')))


def matches_progress(row, selected):
    if selected is None: return True
    progress=purchase_progress(draft_from_record(row),bool(row['cancelled_at']))
    if progress['state']=='cancelled': return False
    if selected=='nationalization_pending':
        return bool(set(progress['pending_categories']) & {'importation','taxes'})
    if selected=='shipping_pending': return 'international_shipping' in progress['pending_categories']
    return selected==progress['state']
