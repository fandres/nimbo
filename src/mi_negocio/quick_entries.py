"""Durable incomplete rows and atomic promotion to ordinary operations."""
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from .storage import operation, StorageError
from .catalog import ValidationError
from .sales import SaleDraft, SaleLineInput, ReceiptInput, money, calculate_totals
from .expenses import ExpenseDraft
from .sales_repository import SalesRepository
from .expenses_repository import ExpensesRepository
from .settings_repository import SettingsRepository
from .commissions import effective_fee


def migrate_quick_entries(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS quick_entries(
        id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('sales','expenses')),
        payload TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
        operation_id INTEGER, revision INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    connection.execute('CREATE INDEX IF NOT EXISTS quick_pending ON quick_entries(kind,operation_id)')
    connection.execute('CREATE TABLE IF NOT EXISTS quick_entry_settings(id INTEGER PRIMARY KEY CHECK(id=1),include_provisional INTEGER NOT NULL DEFAULT 0 CHECK(include_provisional IN (0,1)))')
    connection.execute('INSERT OR IGNORE INTO quick_entry_settings(id) VALUES(1)')
    connection.execute('PRAGMA user_version=29')


def day(text):
    for pattern in ('%Y-%m-%d','%d/%m/%Y'):
        try:return datetime.strptime(text.strip(),pattern).date()
        except ValueError:pass
    raise ValueError('Completa la fecha (dd/mm/aaaa).')


def yes(text):
    value=text.strip().casefold()
    if value in ('sí','si','yes','1'):return True
    if value in ('no','0'):return False
    raise ValueError('Indica Sí o No en cobrado/pagado y retención.')


def match(text, rows, label):
    choices=[r for r in rows if text.strip().casefold() in (str(r['id']),r['name'].casefold())]
    if len(choices)!=1:raise ValueError('Selecciona '+label+' de las opciones disponibles.')
    return choices[0]['id']


class QuickEntriesRepository:
    def __init__(self,connection,preferences=None):
        self.connection=connection
        self.preferences=preferences

    def include_provisional(self):
        return bool(self.connection.execute('SELECT include_provisional FROM quick_entry_settings WHERE id=1').fetchone()[0])

    def set_include_provisional(self,value):
        with operation(self.connection):
            self.connection.execute('UPDATE quick_entry_settings SET include_provisional=? WHERE id=1',(int(bool(value)),))

    def get(self,key):
        row=self.connection.execute('SELECT * FROM quick_entries WHERE id=?',(key,)).fetchone()
        if row is None:raise StorageError('La fila ya no existe. Actualiza el listado.')
        result=dict(row);result['payload']=json.loads(row['payload']);return result

    def pending(self,kind):
        return [self.get(r[0]) for r in self.connection.execute('SELECT id FROM quick_entries WHERE kind=? AND operation_id IS NULL ORDER BY updated_at,id',(kind,))]

    def discard(self,key,revision):
        with operation(self.connection):
            cursor=self.connection.execute('DELETE FROM quick_entries WHERE id=? AND revision=? AND operation_id IS NULL',(key,revision))
            if cursor.rowcount!=1:raise StorageError('La fila cambió o ya fue registrada. Actualiza antes de quitarla.')

    def save(self,kind,payload,key=None,revision=None):
        if kind not in ('sales','expenses'):raise ValueError('Tipo no válido')
        payload={k:str(v).strip() for k,v in payload.items()}
        key=key or uuid4().hex
        with operation(self.connection):
            existing=self.connection.execute('SELECT id FROM quick_entries WHERE id=?',(key,)).fetchone()
            if existing:
                old=self.get(key)
                if old['kind']!=kind:raise StorageError('Tipo de fila diferente.')
                if old['operation_id'] is not None:
                    if old['payload']!=payload:raise StorageError('La fila ya fue registrada con otros datos. Cierra y vuelve a abrir para consultar la operación guardada.')
                    return old
                if old['revision']!=revision:raise StorageError('Esta fila cambió en otra ventana. Cierra y vuelve a abrir el ingreso rápido.')
                self.connection.execute('UPDATE quick_entries SET payload=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?',(json.dumps(payload),key))
            else:
                if revision is not None:raise StorageError('La fila ya no existe.')
                self.connection.execute('INSERT INTO quick_entries(id,kind,payload) VALUES(?,?,?)',(key,kind,json.dumps(payload)))
            try:
                # Nested savepoint rolls back every financial effect on failure.
                with operation(self.connection):
                    result=self._post(kind,payload,'quick-'+key)
                self.connection.execute("UPDATE quick_entries SET operation_id=?,error='' WHERE id=?",(result['id'],key))
            except (ValidationError,ValueError,ArithmeticError,StorageError) as exc:
                # Physical storage failures must abort, not masquerade as incomplete data.
                if isinstance(exc,StorageError) and exc.__cause__ is not None:raise
                message=' · '.join(exc.errors.values()) if isinstance(exc,ValidationError) else str(exc)
                self.connection.execute('UPDATE quick_entries SET error=? WHERE id=?',(message,key))
            return self.get(key)

    def _post(self,kind,p,request):
        required=['date','amount','paid']+(['customer','product','quantity','method','account','vat','withholding'] if kind=='sales' else ['concept','category'])
        labels={'date':'fecha','amount':'importe','paid':'cobrado / pagado','customer':'cliente','product':'producto','quantity':'cantidad','method':'forma de pago','account':'cuenta','vat':'IVA','withholding':'retención','concept':'concepto','category':'categoría'}
        missing=[labels[k] for k in required if not p.get(k)]
        if missing:raise ValueError('Por completar: '+', '.join(missing)+'.')
        when=day(p['date']);paid=yes(p['paid']);settings=SettingsRepository(self.connection)
        if not paid and p.get('paid_on'):
            raise ValueError('Hay fecha de cobro / pago, pero está marcado No. Borra la fecha o marca Sí.')
        paid_on=day(p.get('paid_on','')) if paid else None
        if kind=='expenses':
            category=match(p['category'],ExpensesRepository(self.connection).categories(),'la categoría')
            account=match(p.get('account',''),[vars(a) for a in settings.list_accounts(include_cards=True)],'la cuenta') if paid else None
            if not paid and p.get('account'):raise ValueError('Un gasto sin pagar no tiene cuenta de pago: borra la cuenta o marca Pagado.')
            return ExpensesRepository(self.connection).save(ExpenseDraft(p['concept'],money(p['amount']),when,category,paid_on,account,note=p.get('note',''),voucher=p.get('invoice','')),request_id=request)
        product_rows=[dict(r) for r in self.connection.execute('SELECT id,code,name FROM products WHERE active=1')]
        products=[r for r in product_rows if p['product'].casefold() in (r['code'].casefold(),r['name'].casefold(),(r['code']+' · '+r['name']).casefold())]
        if len(products)!=1:raise ValueError('Selecciona un producto o código activo sin ambigüedad.')
        quantity=int(p['quantity'])
        if quantity<=0:raise ValueError('La cantidad debe ser un entero mayor que cero.')
        methods=settings.list_methods();method_id=match(p['method'],[vars(m) for m in methods],'la forma de pago')
        method=next(m for m in methods if m.id==method_id)
        account=match(p['account'],[vars(a) for a in settings.list_accounts()],'la cuenta')
        withheld=yes(p['withholding'])
        if self.preferences and self.preferences.require_sale_identification() and not p.get('identification'):
            raise ValueError('Completa la cédula / NIT del cliente (Configuración).')
        if withheld and (self.preferences is None or self.preferences.require_retention_documents()) and (not p.get('invoice') or not p.get('email')):
            raise ValueError('Completa factura y correo del cliente para la retención (Configuración).')
        mode=p['vat'].casefold()
        if mode not in ('no aplica','sumar iva','iva incluido'):raise ValueError('IVA: elige No aplica, Sumar IVA o IVA incluido.')
        rate=Decimal(p.get('rate','19')) if mode!='no aplica' else Decimal(19)
        lines=(SaleLineInput(products[0]['id'],quantity,money(p['amount'])),)
        draft=SaleDraft(when,p.get('invoice',''),lines,method.id,account,customer_name=p['customer'],has_withholding=withheld,customer_identification=p.get('identification',''),customer_email=p.get('email',''),vat_enabled=mode!='no aplica',vat_rate=rate,vat_included=mode=='iva incluido',customer_alias=p.get('alias',''),customer_phone=p.get('phone',''))
        totals=calculate_totals(lines,0,0,Decimal(0),0,vat_enabled=draft.vat_enabled,vat_rate=rate,vat_included=draft.vat_included)
        fee,fixed=effective_fee(method,totals.total_cents)
        totals=calculate_totals(lines,0,0,fee,fixed,vat_enabled=draft.vat_enabled,vat_rate=rate,vat_included=draft.vat_included)
        receipt=ReceiptInput(paid_on,account,totals.commission_cents) if paid else None
        return SalesRepository(self.connection).create(draft,request_id=request,expected_method=method,receipt=receipt)
