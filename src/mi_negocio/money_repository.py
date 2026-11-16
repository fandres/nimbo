"""Real cash movements, sourced once; card accounts carry negative debt."""
from datetime import date
from .storage import StorageError, operation
from .withholding import ACCOUNT_ID, ACCOUNT_NAME, deducted
from .sales import check_cents, MAX_CENTS
from .expenses import valid_day
from .expenses_repository import timestamp, payload

KINDS={'transfer':'Transferencia entre cuentas','contribution':'Aporte del propietario',
       'withdrawal':'Retiro del propietario','loan_disbursement':'Desembolso de préstamo',
       'purchase_payment':'Pago de compra','card_payment':'Pago de tarjeta','refund':'Devolución recibida'}
PURCHASE_CATEGORIES={'merchandise':'Mercancía','international_shipping':'Envío internacional',
                     'importation':'Nacionalización / manejo','taxes':'Impuestos','other':'Otros costos'}

class MoneyRepository:
    def __init__(self,connection):self.connection=connection

    def _accounts(self):
        accounts=[dict(r) for r in self.connection.execute('''SELECT a.*,c.id card_id,o.opened_on,o.amount_cents opening_cents,o.revision
            FROM accounts a LEFT JOIN credit_cards c ON c.account_id=a.id
            LEFT JOIN account_openings o ON o.account_id=a.id ORDER BY a.id''')]
        if self.connection.execute('SELECT 1 FROM sales WHERE withholding_deducted=1 AND has_withholding=1 LIMIT 1').fetchone():
            accounts.append(dict(id=ACCOUNT_ID,name=ACCOUNT_NAME,enabled=1,kind='withholding',is_default=0,
                card_id=None,opened_on='0001-01-01',amount_cents=0,opening_cents=0,revision=1))
        return accounts

    def _account(self,key,card=None):
        if key==ACCOUNT_ID:raise StorageError('Retenciones de renta es una cuenta auxiliar automática, no una cuenta de pagos.')
        row=next((a for a in self._accounts() if a['id']==key),None)
        if not row or not row['enabled']:raise StorageError('Selecciona una cuenta habilitada.')
        if card is not None and bool(row['card_id'])!=card:raise StorageError('Selecciona una tarjeta.' if card else 'Selecciona efectivo o banco.')
        if row['card_id']:
            from .credit_cards import CreditCardsRepository
            if not CreditCardsRepository(self.connection).enabled():raise StorageError('Activa el control de tarjetas en Configuración.')
        return row

    def _audit(self,entity,key,description,data):
        self.connection.execute('INSERT INTO money_events(entity,entity_id,changed_at,description,snapshot) VALUES(?,?,?,?,?)',
                                (entity,key,timestamp(),description,payload(data)))

    def set_opening(self,account_id,opened_on,amount_cents,expected_revision=None):
        valid_day(opened_on,'Fecha de inicio')
        if type(amount_cents) is not int or abs(amount_cents)>MAX_CENTS:raise StorageError('Saldo inicial inválido.')
        with operation(self.connection):
            account=self._account(account_id)
            if account['card_id'] and amount_cents>0:raise StorageError('La deuda inicial debe registrarse como saldo negativo.')
            old=self.connection.execute('SELECT * FROM account_openings WHERE account_id=?',(account_id,)).fetchone()
            if old and old['revision']!=expected_revision:raise StorageError('El saldo inicial cambió. Abre nuevamente el formulario.')
            self.connection.execute('''INSERT INTO account_openings(account_id,opened_on,amount_cents) VALUES(?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET opened_on=excluded.opened_on,amount_cents=excluded.amount_cents,revision=account_openings.revision+1''',
                (account_id,str(opened_on),amount_cents))
            self._audit('opening',account_id,'Saldo inicial',dict(date=str(opened_on),amount=amount_cents))

    def add(self,kind,on,amount_cents,concept,from_account=None,to_account=None,*,request_id,purchase_id=None,purchase_category='',capital_cents=None,interest_cents=0,fee_cents=0):
        valid_day(on,'Fecha del movimiento');check_cents(amount_cents)
        if kind not in KINDS or not amount_cents or not concept.strip() or not request_id:raise StorageError('Completa tipo, concepto e importe mayor que cero.')
        capital_cents=amount_cents if capital_cents is None and kind=='card_payment' else (capital_cents or 0)
        for value in (capital_cents,interest_cents,fee_cents):check_cents(value)
        if kind=='card_payment' and capital_cents+interest_cents+fee_cents!=amount_cents:raise StorageError('El desglose del pago no coincide con el total.')
        if kind!='card_payment' and (capital_cents or interest_cents or fee_cents):raise StorageError('El desglose corresponde únicamente a pagos de tarjeta.')
        data=[kind,str(on),amount_cents,concept.strip(),from_account,to_account,purchase_id,purchase_category,capital_cents,interest_cents,fee_cents];raw=payload(data)
        with operation(self.connection):
            old=self.connection.execute('SELECT * FROM money_entries WHERE request_id=?',(request_id,)).fetchone()
            if old:
                if old['request_payload']!=raw:raise StorageError('Esta solicitud ya se guardó con otros datos.')
                return dict(old)
            if kind in ('transfer','card_payment'):
                self._account(from_account,False);self._account(to_account,kind=='card_payment')
                if from_account==to_account:raise StorageError('Selecciona cuentas diferentes.')
            elif kind in ('contribution','loan_disbursement','refund'):
                self._account(to_account,False)
                if from_account is not None:raise StorageError('Este ingreso no tiene cuenta de origen.')
            else:
                self._account(from_account,False if kind=='withdrawal' else None)
                if to_account is not None:raise StorageError('Este pago no tiene cuenta de destino.')
            if kind=='purchase_payment':
                p=self.connection.execute('SELECT cancelled_at FROM purchases WHERE id=?',(purchase_id,)).fetchone()
                if not p or p['cancelled_at']:raise StorageError('Selecciona una compra vigente.')
                if purchase_category not in PURCHASE_CATEGORIES:raise StorageError('Selecciona el concepto pagado de la compra.')
            elif purchase_id is not None or purchase_category:raise StorageError('Solo los pagos de compra pueden asociarse a un pedido.')
            if kind=='card_payment':
                balance=next(a for a in self._balances(on) if a['id']==to_account)
                if not balance['configured']:raise StorageError('Configura primero la deuda inicial de la tarjeta.')
                if amount_cents>max(0,-balance['balance_cents']):raise StorageError('El pago supera la deuda registrada a esa fecha. Revisa cargos e intereses.')
                future_dates={r['date'] for r in self._movements() if r['account_id']==to_account and str(on)<r['date']<=str(date.today())}
                for day in future_dates:
                    later=next(a for a in self._balances(day) if a['id']==to_account)
                    if later['balance_cents']+amount_cents>0:raise StorageError('Este abono, junto con pagos posteriores, supera la deuda. Revisa las fechas e importes.')
            key=self.connection.execute('''INSERT INTO money_entries(kind,occurred_on,amount_cents,concept,from_account,to_account,
                purchase_id,purchase_category,capital_cents,interest_cents,fee_cents,request_id,request_payload,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(*data,request_id,raw,timestamp())).lastrowid
            row=dict(self.connection.execute('SELECT * FROM money_entries WHERE id=?',(key,)).fetchone())
            self._audit('entry',key,'Registro',row)
            return row

    def cancel(self,key,reason):
        if not reason.strip():raise StorageError('Escribe el motivo de anulación.')
        with operation(self.connection):
            row=self.connection.execute('SELECT * FROM money_entries WHERE id=?',(key,)).fetchone()
            if not row or row['cancelled_at']:raise StorageError('El movimiento ya no está vigente.')
            from .credit_cards import CreditCardsRepository
            linked_card = self.connection.execute('SELECT 1 FROM credit_cards WHERE account_id IN (?, ?)', (row['from_account'], row['to_account'])).fetchone()
            if linked_card and not CreditCardsRepository(self.connection).enabled():
                raise StorageError('Activa el control de tarjetas en Configuración para anular este movimiento.')
            self.connection.execute('UPDATE money_entries SET cancelled_at=?,cancellation_reason=? WHERE id=?',(timestamp(),reason.strip(),key))
            self._audit('entry',key,'Anulación: '+reason.strip(),dict(row))

    def history(self,entity,key):
        with operation(self.connection):return [dict(r) for r in self.connection.execute('SELECT * FROM money_events WHERE entity=? AND entity_id=? ORDER BY id',(entity,key))]

    def _movements(self):
        rows=[]
        def add(origin,key,on,account,delta,concept,kind='',detail=''):
            rows.append(dict(origin=origin,source_id=key,date=str(on),account_id=account,delta=delta,concept=concept,kind=kind,detail=detail))
        for r in self.connection.execute('''SELECT s.*,r.received_on,r.account_id,r.commission_cents actual FROM sales s JOIN receipts r ON r.sale_id=s.id WHERE s.cancelled_at IS NULL'''):
            add('sale',r['id'],r['received_on'],r['account_id'],r['total_cents']-r['actual']-deducted(r),'Cobro · '+r['customer_name'],detail='Comisión descontada: '+str(r['actual']))
            if deducted(r):add('sale',r['id'],r['received_on'],ACCOUNT_ID,deducted(r),'Retención de renta · Venta '+str(r['id']),kind='withholding')
        for r in self.connection.execute('''SELECT s.id,s.shipping_cost_cents,p.* FROM sales s JOIN shipping_payments p ON p.sale_id=s.id WHERE s.cancelled_at IS NULL AND s.shipping_enabled=1'''):
            account=r['account_id']
            card=self.connection.execute('SELECT id FROM credit_cards WHERE account_id=?',(account,)).fetchone()
            if r['payment_kind']=='credit_card' and not card:account=None
            if r['shipping_cost_cents']:add('sale',r['id'],r['paid_on'],account,-r['shipping_cost_cents'],'Envío · Venta '+str(r['id']),detail='Sin cuenta asignada' if account is None else '')
        for r in self.connection.execute('SELECT * FROM expenses WHERE paid_on IS NOT NULL AND cancelled_at IS NULL'):
            add('expense',r['id'],r['paid_on'],r['account_id'],-r['amount_cents'],r['concept'])
        for r in self.connection.execute('SELECT p.*,l.name FROM loan_payments p JOIN loans l ON l.id=p.loan_id WHERE p.cancelled_at IS NULL'):
            add('loan',r['loan_id'],r['paid_on'],r['account_id'],-r['capital_cents']-r['interest_cents'],'Cuota · '+r['name'],detail=f"Capital {r['capital_cents']} · Intereses {r['interest_cents']}")
        for r in self.connection.execute('''SELECT m.* FROM money_entries m LEFT JOIN purchases p ON p.id=m.purchase_id
            WHERE m.cancelled_at IS NULL AND (m.purchase_id IS NULL OR p.cancelled_at IS NULL)'''):
            if r['from_account']:add('money',r['id'],r['occurred_on'],r['from_account'],-r['amount_cents'],r['concept'],r['kind'])
            if r['to_account']:add('money',r['id'],r['occurred_on'],r['to_account'],r['amount_cents'],r['concept'],r['kind'])
        for r in self.connection.execute('''SELECT e.*,c.account_id FROM credit_card_charges e JOIN credit_cards c ON c.id=e.card_id WHERE e.cancelled_at IS NULL'''):
            add('card',r['card_id'],r['charged_on'],r['account_id'],-r['interest_cents']-r['fee_cents'],'Intereses y cargos de tarjeta',detail=r['note'])
        names={a['id']:a for a in self._accounts()}
        for r in rows:
            a=names.get(r['account_id'],{})
            r['account']=a.get('name','Sin cuenta · por completar');r['is_card']=bool(a.get('card_id'));r['is_withholding']=r['account_id']==ACCOUNT_ID
        return sorted(rows,key=lambda r:(r['date'],r['origin'],r['source_id']),reverse=True)

    def movements(self,start=None,end=None,account_id=None,query=''):
        with operation(self.connection):
            return [r for r in self._movements() if (start is None or r['date']>=str(start)) and
                (end is None or r['date']<=str(end)) and (account_id is None or r['account_id']==account_id) and
                (not query or query.casefold() in (r['concept']+' '+r['account']).casefold())]

    def _balances(self,as_of):
        rows=self._movements();result=[]
        for a in self._accounts():
            configured=a['opened_on'] is not None and a['opened_on']<=str(as_of)
            balance=a['opening_cents']+sum(r['delta'] for r in rows if r['account_id']==a['id'] and a['opened_on']<=r['date']<=str(as_of)) if configured else None
            result.append(dict(a,is_card=bool(a['card_id']),configured=configured,balance_cents=balance))
        return result

    def balances(self,as_of=None):
        with operation(self.connection):return self._balances(as_of or date.today())

    def snapshot(self,account_id,end):
        # Read-only and safe to call inside reconciliation's write transaction.
        opening=self.connection.execute('SELECT * FROM account_openings WHERE account_id=?',(account_id,)).fetchone()
        return dict(opening=dict(opening) if opening else None,movements=[{k:r[k] for k in ('origin','source_id','date','delta','kind')} for r in self._movements() if r['account_id']==account_id and r['date']<=str(end)])

    def summary(self,start,end,account_id=None):
        if start>end:raise StorageError('Revisa el rango de fechas.')
        with operation(self.connection):
            rows=[r for r in self._movements() if str(start)<=r['date']<=str(end) and (account_id is None or r['account_id']==account_id)]
            flow=[r for r in rows if r['account_id'] is not None and not r['is_card'] and not r['is_withholding'] and (account_id is not None or r['kind']!='transfer')]
            incoming=sum(max(0,r['delta']) for r in flow);outgoing=sum(max(0,-r['delta']) for r in flow)
            balances=self._balances(date.today());selected=[a for a in balances if not a['is_card'] and a['id']!=ACCOUNT_ID and (account_id is None or a['id']==account_id)]
            return dict(incoming=incoming,outgoing=outgoing,net=incoming-outgoing,
                available=sum(a['balance_cents'] for a in selected if a['configured']),missing=sum(not a['configured'] for a in selected),
                unassigned=sum(r['account_id'] is None for r in rows),flow=flow,balances=balances,
                closing=self._balances(end))
