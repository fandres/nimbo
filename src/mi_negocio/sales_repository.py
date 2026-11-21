"""Ventas y pagos atómicos con instantáneas históricas."""
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from uuid import uuid4
from collections import defaultdict
from .withholding import deducted
from .vat import sale_line_amounts
from .commissions import effective_fee, decode_tiers, validate_fee
from .sales import calculate_totals, validate_sale, check_cents, SalesFilter, informative_withholding, SHIPPING_PAYMENT_KINDS
from .storage import StorageError, operation


class SalesRepository:
    def __init__(self, connection): self.connection=connection

    def permissions(self):
        return {r['action']:bool(r['enabled']) for r in self.connection.execute('SELECT * FROM sale_permissions')}

    def set_permission(self, action, enabled):
        if action not in ('edit','cancel','delete'):raise StorageError('Permiso no válido.')
        with operation(self.connection):
            self.connection.execute('UPDATE sale_permissions SET enabled=? WHERE action=?',(int(bool(enabled)),action))

    def _require_permission(self, action):
        if not self.permissions()[action]:
            raise StorageError('Esta acción está deshabilitada en Configuración → Ventas.')

    def history(self, sale_id):
        with operation(self.connection):
            return [dict(r) for r in self.connection.execute('SELECT * FROM sale_revisions WHERE sale_id=? ORDER BY id DESC',(sale_id,))]

    def delete(self, sale_id):
        with operation(self.connection):
            self._require_permission('delete')
            sale=self._get(sale_id)
            from .inventory_repository import cancel_sale
            if not sale['cancelled_at']:cancel_sale(self.connection,sale_id)
            # Keep the sequence beyond deleted IDs: inventory and document paths use them.
            self.connection.execute('UPDATE sale_id_sequence SET last_id=MAX(last_id,?) WHERE id=1',(sale_id,))
            for table in ('receipts','shipping_payments','sale_lines','sale_revisions'):
                self.connection.execute(f'DELETE FROM {table} WHERE sale_id=?',(sale_id,))
            self.connection.execute("DELETE FROM attachments WHERE owner_kind='sale' AND owner_id=?",(sale_id,))
            self.connection.execute('DELETE FROM sales WHERE id=?',(sale_id,))

    def _replace_lines(self, sale, lines):
        self._require_permission('edit')
        totals=calculate_totals(lines,sale['shipping_charged_cents'],sale['shipping_cost_cents'],
            Decimal(sale['rate_percent']),sale['fixed_cents'],vat_enabled=bool(sale['vat_enabled']),
            vat_rate=Decimal(sale['vat_rate']),vat_included=bool(sale['vat_included']))
        old={l['product_id']:l for l in sale['lines']}
        products={}
        for line in lines:
            p=self.connection.execute('SELECT * FROM products WHERE id=?',(line.product_id,)).fetchone()
            if not p or (not p['active'] and line.product_id not in old):
                raise StorageError('Selecciona un producto activo del catálogo.')
            products[line.product_id]=p
        from .inventory_repository import move
        tracked=sale['stock_tracked']
        if tracked:
            delta=defaultdict(int)
            consumed=self.connection.execute('SELECT product_id,SUM(delta) AS delta FROM inventory_movements WHERE operation_key=? OR operation_key LIKE ? GROUP BY product_id',
                (f"sale:{sale['id']}",f"sale-edit:{sale['id']}:%")).fetchall()
            for movement in consumed:delta[movement['product_id']]-=movement['delta']
            for line in lines:
                if products[line.product_id]['kind']=='product':delta[line.product_id]-=line.quantity
            operation_key=f"sale-edit:{sale['id']}:{uuid4().hex}"
            for product_id,change in delta.items():
                if change:move(self.connection,product_id,change,operation_key,'sale',f"Corrección de venta #{sale['id']}")
        self.connection.execute('DELETE FROM sale_lines WHERE sale_id=?',(sale['id'],))
        for line,total in zip(lines,sale_line_amounts(lines,bool(sale['vat_enabled']),Decimal(sale['vat_rate']),bool(sale['vat_included']))):
            p=old.get(line.product_id,products[line.product_id])
            self.connection.execute('INSERT INTO sale_lines(sale_id,product_id,code,name,quantity,unit_price_cents,line_total_cents) VALUES(?,?,?,?,?,?,?)',
                (sale['id'],line.product_id,p['code'],p['name'],line.quantity,line.unit_price_cents,total))
        self.connection.execute('UPDATE sales SET subtotal_cents=?,total_cents=?,commission_cents=?,base_cents=?,vat_cents=? WHERE id=?',
            (totals.subtotal_cents,totals.total_cents,totals.commission_cents,totals.base_cents,totals.vat_cents,sale['id']))

    def _account(self, key, allow_card=False):
        if not self.connection.execute('SELECT id FROM accounts WHERE id=? AND enabled=1',(key,)).fetchone():
            raise StorageError('Selecciona una cuenta activa.')
        card=self.connection.execute('SELECT 1 FROM credit_cards WHERE account_id=?',(key,)).fetchone()
        if card and (not allow_card or not self.connection.execute('SELECT enabled FROM credit_card_settings WHERE id=1').fetchone()[0]):
            raise StorageError('Para usar esta tarjeta activa su control y selecciona pago con tarjeta crédito.')

    def _get(self, key):
        row=self.connection.execute('SELECT s.*, a.name AS account_name FROM sales s JOIN accounts a ON a.id=s.destination_account_id WHERE s.id=?',(key,)).fetchone()
        if row is None: raise StorageError('La venta no existe.')
        result=dict(row)
        result['lines']=[dict(r) for r in self.connection.execute('SELECT * FROM sale_lines WHERE sale_id=? ORDER BY id',(key,))]
        for name,table in [('receipt','receipts'),('shipping_payment','shipping_payments')]:
            r=self.connection.execute(f'SELECT p.*,a.name AS account_name FROM {table} p LEFT JOIN accounts a ON a.id=p.account_id WHERE sale_id=?',(key,)).fetchone()
            result[name]=dict(r) if r else None
        result['withholding_cents']=informative_withholding(result['total_cents']) if result['has_withholding'] else 0
        result['received']=result['receipt'] is not None
        actual=result['receipt']['commission_cents'] if result['receipt'] else result['commission_cents']
        result['deposit_cents']=result['total_cents']-actual-deducted(result)
        result['net_after_shipping_cents']=result['deposit_cents']-result['shipping_cost_cents']
        return result

    def _editable(self, sale_id):
        sale=self._get(sale_id)
        if sale['cancelled_at']:
            raise StorageError('Esta venta está anulada y se conserva solo para consulta.')
        return sale

    def cancel(self, sale_id, reason=''):
        with operation(self.connection):
            self._require_permission('cancel')
            sale=self._get(sale_id)
            if not sale['cancelled_at']:
                from .inventory_repository import cancel_sale
                cancel_sale(self.connection,sale_id)
                self.connection.execute('UPDATE sales SET cancelled_at=?,cancellation_reason=? WHERE id=?',
                    (datetime.now(timezone.utc).isoformat(),reason.strip(),sale_id))
            return self._get(sale_id)

    def get(self, sale_id):
        with operation(self.connection): return self._get(sale_id)

    def create(self,draft,*,request_id,expected_method,receipt=None,shipping_payment=None):
        validate_sale(draft)
        if not request_id: raise StorageError('Falta el identificador de guardado.')
        payload=json.dumps([asdict(draft),asdict(expected_method),asdict(receipt) if receipt else None,asdict(shipping_payment) if shipping_payment else None],default=str,sort_keys=True)
        with operation(self.connection):
            existing=self.connection.execute('SELECT id,request_payload FROM sales WHERE request_id=?',(request_id,)).fetchone()
            if existing:
                if existing['request_payload']!=payload: raise StorageError('La solicitud ya fue guardada con otros datos. Abre una nueva venta.')
                return self._get(existing['id'])
            method=self.connection.execute('SELECT * FROM payment_methods WHERE id=? AND enabled=1',(draft.method_id,)).fetchone()
            if not method or expected_method.id!=draft.method_id:
                raise StorageError('La forma de pago ya no está habilitada. Actualiza las opciones.')
            snapshot=(method['name'],method['provider'],Decimal(method['rate_percent']),method['fixed_cents'],method['placement'],bool(method['default_received']),method['account_kind'],decode_tiers(method['tiers_json']))
            expected=(expected_method.name,expected_method.provider,expected_method.rate_percent,expected_method.fixed_cents,expected_method.placement,expected_method.default_received,expected_method.account_kind,expected_method.tiers)
            if snapshot!=expected: raise StorageError('Cambió la configuración de pago. Actualiza las opciones y revisa los importes.')
            self._account(draft.destination_account_id)
            if method['account_kind']=='bank' and self.connection.execute('SELECT kind FROM accounts WHERE id=?',(draft.destination_account_id,)).fetchone()[0]!='bank':
                raise StorageError('Para esta forma de pago elige una cuenta bancaria o billetera.')
            base=calculate_totals(draft.lines,draft.shipping_charged_cents,draft.shipping_cost_cents,Decimal(0),0,vat_enabled=draft.vat_enabled,vat_rate=draft.vat_rate,vat_included=draft.vat_included)
            rate,fixed=draft.commission_override if draft.commission_override is not None else effective_fee(expected_method,base.total_cents)
            validate_fee(rate,fixed)
            totals=calculate_totals(draft.lines,draft.shipping_charged_cents,draft.shipping_cost_cents,rate,fixed,vat_enabled=draft.vat_enabled,vat_rate=draft.vat_rate,vat_included=draft.vat_included)
            values=(request_id,payload,draft.sold_on.isoformat(),draft.invoice_ref.strip(),draft.method_id,method['name'],method['provider'],str(rate),fixed,draft.destination_account_id,int(draft.shipping_enabled),draft.shipping_charged_cents,draft.shipping_cost_cents,totals.subtotal_cents,totals.total_cents,totals.commission_cents)
            next_id=self.connection.execute('SELECT MAX(last_id,(SELECT COALESCE(MAX(id),0) FROM sales))+1 FROM sale_id_sequence WHERE id=1').fetchone()[0]
            self.connection.execute('UPDATE sale_id_sequence SET last_id=? WHERE id=1',(next_id,))
            values=(next_id,)+values
            key=self.connection.execute('INSERT INTO sales(id,request_id,request_payload,sold_on,invoice_ref,method_id,method_name,provider,rate_percent,fixed_cents,destination_account_id,shipping_enabled,shipping_charged_cents,shipping_cost_cents,subtotal_cents,total_cents,commission_cents) VALUES('+','.join('?' for _ in values)+')',values).lastrowid
            self.connection.execute('UPDATE sales SET vat_enabled=?,vat_rate=?,vat_included=?,base_cents=?,vat_cents=? WHERE id=?',(int(draft.vat_enabled),str(draft.vat_rate),int(draft.vat_included),totals.base_cents,totals.vat_cents,key))
            self.connection.execute('UPDATE sales SET withholding_deducted=1 WHERE id=?',(key,))
            self.connection.execute('UPDATE sales SET customer_alias=?,customer_phone=? WHERE id=?',(draft.customer_alias.strip(),draft.customer_phone.strip(),key))
            carrier_name = ''
            if draft.carrier_id is not None:
                carrier = self.connection.execute('SELECT name FROM carriers WHERE id=? AND enabled=1',(draft.carrier_id,)).fetchone()
                if not carrier or not draft.shipping_enabled:
                    raise StorageError('Selecciona una transportadora activa para el envío.')
                carrier_name = carrier['name']
            self.connection.execute('UPDATE sales SET customer_name=?,carrier_id=?,carrier_name=?,destination_city=?,has_withholding=?,tracking_number=?,customer_identification=?,customer_email=? WHERE id=?',
                (draft.customer_name.strip(),draft.carrier_id,carrier_name,draft.destination_city.strip() if draft.shipping_enabled else '',int(draft.has_withholding),draft.tracking_number.strip() if draft.shipping_enabled else '',draft.customer_identification.strip(),draft.customer_email.strip(),key))
            for line,line_total in zip(draft.lines,sale_line_amounts(draft.lines,draft.vat_enabled,draft.vat_rate,draft.vat_included)):
                p=self.connection.execute('SELECT code,name FROM products WHERE id=? AND active=1',(line.product_id,)).fetchone()
                if not p: raise StorageError('Un producto ya no está activo. Revisa el catálogo.')
                self.connection.execute('INSERT INTO sale_lines(sale_id,product_id,code,name,quantity,unit_price_cents,line_total_cents) VALUES(?,?,?,?,?,?,?)',(key,line.product_id,p['code'],p['name'],line.quantity,line.unit_price_cents,line_total))
            from .inventory_repository import sale_out
            sale_out(self.connection,key,draft.lines)
            self.connection.execute('UPDATE sales SET stock_tracked=(SELECT initialized FROM inventory_state WHERE id=1) WHERE id=?',(key,))
            self._validate_withholding(self._get(key),draft.has_withholding,receipt.commission_cents if receipt else None)
            if receipt: self._receipt(key,receipt)
            if shipping_payment: self._shipping(key,shipping_payment)
            return self._get(key)

    def _validate_withholding(self,sale,enabled,commission=None):
        proposed=dict(sale,has_withholding=enabled)
        if commission is None:
            commission=sale['receipt']['commission_cents'] if sale['receipt'] else sale['commission_cents']
        if commission+deducted(proposed)>sale['total_cents']:
            raise StorageError('La comisión y la retención superan el total cobrado.')

    def _receipt(self,key,receipt):
        sale=self._editable(key)
        if sale['receipt']: raise StorageError('Esta venta ya tiene un cobro registrado.')
        check_cents(receipt.commission_cents)
        if not date.fromisoformat(sale['sold_on'])<=receipt.received_on<=date.today():
            raise StorageError('La fecha de cobro debe estar entre la venta y hoy.')
        if receipt.commission_cents+deducted(sale)>sale['total_cents']: raise StorageError('La comisión y la retención superan el total cobrado.')
        self._account(receipt.account_id)
        method=self.connection.execute('SELECT account_kind FROM payment_methods WHERE id=?',(sale['method_id'],)).fetchone()
        if method and method[0]=='bank':
            account=self.connection.execute('SELECT kind FROM accounts WHERE id=?',(receipt.account_id,)).fetchone()
            if account[0]!='bank':raise StorageError('Para esta forma de pago elige una cuenta bancaria o billetera.')
        self.connection.execute('INSERT INTO receipts VALUES(?,?,?,?)',(key,receipt.received_on.isoformat(),receipt.account_id,receipt.commission_cents))

    def _set_payment_method(self,sale,method):
        if sale['receipt']:raise StorageError('La forma de pago de un cobro registrado se conserva en el historial.')
        self._require_permission('edit')
        from .settings_repository import SettingsRepository
        current=next((m for m in SettingsRepository(self.connection).list_methods() if m.id==method.id),None)
        if current!=method:raise StorageError('Cambió la forma de pago en Configuración. Cierra y vuelve a abrir para actualizarla.')
        rate,fixed=effective_fee(method,sale['total_cents']);validate_fee(rate,fixed)
        from .sales import SaleLineInput
        total=calculate_totals((SaleLineInput(0,1,sale['total_cents']),),0,0,rate,fixed)
        self.connection.execute('UPDATE sales SET method_id=?,method_name=?,provider=?,rate_percent=?,fixed_cents=?,commission_cents=? WHERE id=?',
            (method.id,method.name,method.provider,str(rate),fixed,total.commission_cents,sale['id']))

    def confirm_receipt(self,sale_id,receipt,*,payment_method=None,expected_sale=None):
        with operation(self.connection):
            self._require_permission('edit')
            before=self._editable(sale_id)
            if expected_sale is not None and before!=expected_sale:
                raise StorageError('La venta cambió desde que abriste el cobro. Cierra y vuelve a abrir para revisar los datos actuales.')
            if payment_method is not None:self._set_payment_method(before,payment_method)
            self._receipt(sale_id,receipt)
            after=self._get(sale_id)
            self.connection.execute('INSERT INTO sale_revisions(sale_id,created_at,before_json,after_json) VALUES(?,?,?,?)',
                (sale_id,datetime.now(timezone.utc).isoformat(),json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False)))
            return after

    def _shipping(self,key,payment):
        sale=self._editable(key)
        if sale['shipping_payment']: raise StorageError('El envío ya está pagado.')
        if not sale['shipping_enabled'] or sale['shipping_cost_cents']<=0: raise StorageError('Esta venta no tiene costo de envío pendiente.')
        if payment.paid_on>date.today(): raise StorageError('La fecha de pago no puede ser futura.')
        if payment.account_id is not None:self._account(payment.account_id,payment.payment_kind=='credit_card')
        if payment.payment_kind not in SHIPPING_PAYMENT_KINDS:
            raise StorageError('Selecciona una forma de pago del envío válida.')
        self.connection.execute('INSERT INTO shipping_payments(sale_id,paid_on,account_id,payment_kind) VALUES(?,?,?,?)',(key,payment.paid_on.isoformat(),payment.account_id,payment.payment_kind))

    def pay_shipping(self,sale_id,payment):
        with operation(self.connection):
            self._shipping(sale_id,payment)
            return self._get(sale_id)

    def update_shipping_payment_details(self, sale_id, account_id, payment_kind):
        with operation(self.connection):
            if not self._editable(sale_id)['shipping_payment']:
                raise StorageError('Primero registra el pago del envío.')
            if account_id is not None:self._account(account_id,payment_kind=='credit_card')
            if payment_kind not in SHIPPING_PAYMENT_KINDS:
                raise StorageError('Selecciona una forma de pago del envío válida.')
            self.connection.execute('UPDATE shipping_payments SET account_id=?,payment_kind=? WHERE sale_id=?',(account_id,payment_kind,sale_id))
            return self._get(sale_id)

    def save_detail(self, sale_id, *, invoice_ref, has_withholding, tracking_number,
                    receipt=None, shipping_payment=None, shipping_details=None, customer_email=None, customer_alias=None, customer_phone=None, lines=None, payment_method=None, expected_sale=None):
        """Guarda el formulario completo en una sola transacción."""
        with operation(self.connection):
            self._require_permission('edit')
            sale = self._editable(sale_id)
            before=sale
            if expected_sale is not None and before!=expected_sale:raise StorageError('La venta cambió. Cierra y vuelve a abrir para actualizar los datos.')
            if lines is not None:
                self._replace_lines(sale,lines)
                sale=self._get(sale_id)
            if payment_method is not None:
                self._set_payment_method(sale,payment_method);sale=self._get(sale_id)
            self._validate_withholding(sale,has_withholding,receipt.commission_cents if receipt else None)
            self.connection.execute('UPDATE sales SET has_withholding=? WHERE id=?',(int(has_withholding),sale_id))
            if receipt is not None:
                self._receipt(sale_id, receipt)
            if shipping_payment is not None:
                self._shipping(sale_id, shipping_payment)
            if shipping_details is not None:
                if not sale['shipping_payment']:
                    raise StorageError('El pago del envío todavía no está registrado.')
                account_id, payment_kind = shipping_details
                if account_id is not None:self._account(account_id,payment_kind=='credit_card')
                if payment_kind not in SHIPPING_PAYMENT_KINDS:
                    raise StorageError('Selecciona una forma de pago del envío válida.')
                self.connection.execute('UPDATE shipping_payments SET account_id=?,payment_kind=? WHERE sale_id=?',(account_id,payment_kind,sale_id))
            self.connection.execute('UPDATE sales SET invoice_ref=?,has_withholding=?,tracking_number=? WHERE id=?',
                (invoice_ref.strip(),int(has_withholding),tracking_number.strip() if sale['shipping_enabled'] else '',sale_id))
            for field,value in (('customer_alias',customer_alias),('customer_phone',customer_phone)):
                if value is not None:self.connection.execute(f'UPDATE sales SET {field}=? WHERE id=?',(value.strip(),sale_id))
            if customer_email is not None:
                self.connection.execute('UPDATE sales SET customer_email=? WHERE id=?',(customer_email.strip(),sale_id))
            after=self._get(sale_id)
            if before!=after:
                self.connection.execute('INSERT INTO sale_revisions(sale_id,created_at,before_json,after_json) VALUES(?,?,?,?)',
                    (sale_id,datetime.now(timezone.utc).isoformat(),json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False)))
            return after

    def update_invoice(self,sale_id,reference,has_withholding=None):
        with operation(self.connection):
            self._require_permission('edit')
            self._editable(sale_id)
            if self.connection.execute('UPDATE sales SET invoice_ref=? WHERE id=?',(reference.strip(),sale_id)).rowcount!=1:
                raise StorageError('La venta no existe.')
            if has_withholding is not None:
                self._validate_withholding(self._get(sale_id),has_withholding)
                self.connection.execute('UPDATE sales SET has_withholding=? WHERE id=?',(int(has_withholding),sale_id))

    def update_tracking(self, sale_id, tracking_number):
        with operation(self.connection):
            self._require_permission('edit')
            sale = self._editable(sale_id)
            if not sale['shipping_enabled']:
                raise StorageError('Esta venta no tiene envío.')
            self.connection.execute('UPDATE sales SET tracking_number=? WHERE id=?',(tracking_number.strip(),sale_id))

    def list_sales(self,filters=SalesFilter()):
        clauses=[]; args=[]
        if filters.cancelled is not None:
            clauses.append('s.cancelled_at IS '+('NOT NULL' if filters.cancelled else 'NULL'))
        for column,operator,value in [('s.sold_on','>=',filters.start),('s.sold_on','<=',filters.end),('COALESCE(r.account_id,s.destination_account_id)','=',filters.account_id)]:
            if value is not None:
                clauses.append(column+operator+'?');args.append(value.isoformat() if isinstance(value,date) else value)
        if filters.vat_enabled is not None:
            clauses.append('s.vat_enabled=?');args.append(int(filters.vat_enabled))
        if filters.has_withholding is not None:
            clauses.append('s.has_withholding=?');args.append(int(filters.has_withholding))
        if filters.received is not None: clauses.append('r.sale_id IS '+('NOT NULL' if filters.received else 'NULL'))
        if filters.query:
            clauses.append('(instr(casefold(s.invoice_ref),?)>0 OR instr(casefold(s.customer_name),?)>0 OR instr(casefold(s.customer_alias),?)>0 OR instr(casefold(s.customer_phone),?)>0 OR EXISTS(SELECT 1 FROM sale_lines l WHERE l.sale_id=s.id AND (instr(casefold(l.code),?)>0 OR instr(casefold(l.name),?)>0)))')
            args.extend([filters.query.casefold()]*6)
        with operation(self.connection):
            rows=self.connection.execute('SELECT s.*, a.name AS account_name, r.sale_id IS NOT NULL AS received, COALESCE(r.commission_cents,s.commission_cents) AS actual_commission_cents FROM sales s LEFT JOIN receipts r ON r.sale_id=s.id JOIN accounts a ON a.id=COALESCE(r.account_id,s.destination_account_id)'+(' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY s.sold_on DESC,s.id DESC',args).fetchall()
        return [dict(r,withholding_cents=informative_withholding(r['total_cents']) if r['has_withholding'] else 0) for r in rows]

    def list_lines(self, sale_ids):
        """Historical labels/prices and current catalog classification, in bounded batches."""
        ids=list(dict.fromkeys(sale_ids));result=[]
        if not ids:return result
        with operation(self.connection):
            for offset in range(0,len(ids),500):
                batch=ids[offset:offset+500]
                result.extend(dict(row) for row in self.connection.execute(
                    'SELECT l.*,p.kind FROM sale_lines l JOIN products p ON p.id=l.product_id WHERE l.sale_id IN ('+
                    ','.join('?' for _ in batch)+') ORDER BY l.id DESC',batch))
        return result

    def shipping_cities(self):
        with operation(self.connection):
            rows=self.connection.execute("SELECT MIN(TRIM(destination_city)) AS city FROM sales WHERE TRIM(destination_city)<>'' GROUP BY casefold(TRIM(destination_city)) ORDER BY casefold(TRIM(destination_city))").fetchall()
            return [row['city'] for row in rows]

    def home_summary(self,today):
        sales=self.list_sales()
        monthly=[s for s in sales if today.replace(day=1).isoformat()<=s['sold_on']<=today.isoformat()]
        pending=[s for s in sales if not s['received']]
        return dict(month_subtotal_cents=sum(s['subtotal_cents'] for s in monthly),month_shipping_cents=sum(s['shipping_charged_cents'] for s in monthly),pending_total_cents=sum(s['total_cents'] for s in pending),pending_count=len(pending),recent_sales=sales[:3])
