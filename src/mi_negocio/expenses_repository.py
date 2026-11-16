"""Gastos manuales y vista unificada de costos, sin duplicar sus orígenes."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from .expenses import ExpenseFilter, validate_expense
from .storage import operation, StorageError


def timestamp():return datetime.now(timezone.utc).isoformat()
def payload(value):return json.dumps(value,default=str,ensure_ascii=False,sort_keys=True)


def check_account(connection,key,previous=None):
    row=connection.execute('SELECT enabled FROM accounts WHERE id=?',(key,)).fetchone()
    card=connection.execute('SELECT 1 FROM credit_cards WHERE account_id=?',(key,)).fetchone()
    if card and key!=previous and not connection.execute('SELECT enabled FROM credit_card_settings WHERE id=1').fetchone()[0]:
        raise StorageError('Activa el control de tarjetas en Configuración.')
    if not row or (not row['enabled'] and key!=previous):
        raise StorageError('Selecciona una cuenta habilitada para registrar el pago.')


class ExpensesRepository:
    def __init__(self,connection):self.connection=connection

    def categories(self,include_disabled=False):
        with operation(self.connection):
            return [dict(r) for r in self.connection.execute('SELECT * FROM expense_categories'+('' if include_disabled else ' WHERE enabled=1')+' ORDER BY id')]

    def concept_suggestions(self,text):
        query=text.strip().casefold()
        if len(query)<3:return []
        with operation(self.connection):
            rows=self.connection.execute("""SELECT e.concept,e.category_id,c.name category,c.enabled
                FROM expenses e JOIN expense_categories c ON c.id=e.category_id
                WHERE e.cancelled_at IS NULL AND instr(casefold(e.concept),?)>0
                ORDER BY e.updated_at DESC,e.id DESC""",(query,)).fetchall()
        seen=set();result=[]
        for row in rows:
            key=row['concept'].strip().casefold()
            if key in seen:continue
            seen.add(key)
            if row['enabled']:result.append(dict(row))
            if len(result)==15:break
        return result

    def save_category(self,key,name,enabled=True):
        name=name.strip()
        if not name:raise StorageError('Escribe el nombre de la categoría.')
        with operation(self.connection):
            duplicate=self.connection.execute('SELECT id FROM expense_categories WHERE name_key=?',(name.casefold(),)).fetchone()
            if duplicate and duplicate['id']!=key:raise StorageError('Ya existe una categoría con ese nombre.')
            if key:
                if self.connection.execute('UPDATE expense_categories SET name=?,name_key=?,enabled=? WHERE id=?',(name,name.casefold(),int(enabled),key)).rowcount!=1:raise StorageError('La categoría ya no existe.')
                return key
            return self.connection.execute('INSERT INTO expense_categories(name,name_key,enabled) VALUES(?,?,?)',(name,name.casefold(),int(enabled))).lastrowid

    def _get(self,key):
        row=self.connection.execute('SELECT * FROM expenses WHERE id=?',(key,)).fetchone()
        if not row:raise StorageError('El gasto ya no existe.')
        return dict(row)

    def get(self,key):
        with operation(self.connection):return self._get(key)

    def _audit(self,key):
        row=self._get(key)
        self.connection.execute('INSERT INTO expense_revisions(expense_id,revision,changed_at,snapshot) VALUES(?,?,?,?)',(key,row['revision'],timestamp(),payload(row)))

    def save(self,draft,*,request_id=None,expense_id=None,expected_revision=None):
        validate_expense(draft)
        data=asdict(draft);data['concept']=data['concept'].strip();raw=payload(data)
        with operation(self.connection):
            previous=None
            if expense_id:
                previous=self._get(expense_id)
                if previous['cancelled_at'] or previous['revision']!=expected_revision:raise StorageError('El gasto cambió o fue anulado. Cierra y vuelve a abrir el detalle.')
            else:
                if not request_id:raise StorageError('Falta la identificación del registro.')
                existing=self.connection.execute('SELECT id,request_payload FROM expenses WHERE request_id=?',(request_id,)).fetchone()
                if existing:
                    if existing['request_payload']!=raw:raise StorageError('Esta solicitud ya fue guardada con otros datos.')
                    return self._get(existing['id'])
            category=self.connection.execute('SELECT enabled FROM expense_categories WHERE id=?',(draft.category_id,)).fetchone()
            if not category or (not category['enabled'] and (not previous or previous['category_id']!=draft.category_id)):
                raise StorageError('Selecciona una categoría habilitada.')
            if draft.paid_on:
                # A disabled account may be retained only for the unchanged historical payment.
                keep=previous and previous['paid_on']==str(draft.paid_on) and previous['amount_cents']==draft.amount_cents
                check_account(self.connection,draft.account_id,previous['account_id'] if keep else None)
            values=(data['concept'],draft.amount_cents,str(draft.spent_on),draft.category_id,
                    str(draft.paid_on) if draft.paid_on else None,draft.account_id,
                    str(draft.due_on) if draft.due_on else None,draft.note.strip(),draft.voucher.strip(),timestamp())
            if previous:
                self.connection.execute('''UPDATE expenses SET concept=?,amount_cents=?,spent_on=?,category_id=?,paid_on=?,account_id=?,due_on=?,note=?,voucher=?,updated_at=?,revision=revision+1 WHERE id=?''',(*values,expense_id))
                key=expense_id
            else:
                key=self.connection.execute('''INSERT INTO expenses(concept,amount_cents,spent_on,category_id,paid_on,account_id,due_on,note,voucher,updated_at,created_at,request_id,request_payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(*values,timestamp(),request_id,raw)).lastrowid
            self._audit(key)
            return self._get(key)

    def cancel(self,key,expected_revision,reason):
        if not reason.strip():raise StorageError('Escribe el motivo de anulación.')
        with operation(self.connection):
            row=self._get(key)
            if row['cancelled_at'] or row['revision']!=expected_revision:raise StorageError('El gasto cambió o ya fue anulado. Actualiza la vista.')
            self.connection.execute('UPDATE expenses SET cancelled_at=?,cancellation_reason=?,updated_at=?,revision=revision+1 WHERE id=?',(timestamp(),reason.strip(),timestamp(),key))
            self._audit(key)

    def history(self,key):
        with operation(self.connection):return [dict(r) for r in self.connection.execute('SELECT * FROM expense_revisions WHERE expense_id=? ORDER BY revision',(key,))]

    def _movements(self):
        result=[]
        for r in self.connection.execute('''SELECT e.*,c.name category,a.name account FROM expenses e JOIN expense_categories c ON c.id=e.category_id LEFT JOIN accounts a ON a.id=e.account_id'''):
            result.append(dict(id=r['id'],origin='manual',source_id=r['id'],spent_on=r['spent_on'],concept=r['concept'],category=r['category'],category_key='manual:'+str(r['category_id']),amount_cents=r['amount_cents'],paid=bool(r['paid_on']),paid_on=r['paid_on'],account_id=r['account_id'],account=r['account'] or '—',due_on=r['due_on'],cancelled=bool(r['cancelled_at']),estimated=False,detail='',revision=r['revision'],created_at=r['created_at'],order_id=r['id']))
        query='''SELECT s.*,r.received_on,r.account_id receipt_account,r.commission_cents real_commission,
            p.paid_on shipping_paid,p.account_id shipping_account,p.payment_kind,
            a.name receipt_account_name,b.name shipping_account_name
            FROM sales s LEFT JOIN receipts r ON r.sale_id=s.id LEFT JOIN shipping_payments p ON p.sale_id=s.id
            LEFT JOIN accounts a ON a.id=r.account_id LEFT JOIN accounts b ON b.id=p.account_id'''
        for r in self.connection.execute(query):
            commission=r['real_commission'] if r['received_on'] else r['commission_cents']
            for kind,name,value,paid_on,account_id,account in [
                ('commission','Comisión de venta',commission,r['received_on'],r['receipt_account'],r['receipt_account_name']),
                ('shipping','Envío de venta',r['shipping_cost_cents'] if r['shipping_enabled'] else 0,r['shipping_paid'],r['shipping_account'],r['shipping_account_name'])]:
                if value<=0:continue
                detail='Automático desde Ventas'
                estimated=kind=='commission' and not paid_on
                if kind=='commission':detail+=' · '+(r['provider'] or r['method_name'])
                if estimated:detail+=' · Comisión estimada'
                if kind=='shipping' and r['payment_kind']=='credit_card':detail+=' · Pagado a transportadora con crédito'
                result.append(dict(id=f'{kind}:{r["id"]}',origin='sale',source_id=r['id'],method_id=r['method_id'] if kind=='commission' else None,platform=(r['provider'] or r['method_name']) if kind=='commission' else '',spent_on=r['sold_on'],concept=('Comisión' if kind=='commission' else 'Envío')+' · Venta '+(r['invoice_ref'] or str(r['id'])),category=name,category_key=kind,amount_cents=value,paid=bool(paid_on),paid_on=paid_on,account_id=account_id,account=account or '—',due_on=None,cancelled=bool(r['cancelled_at']),estimated=estimated,detail=detail,created_at=r['sold_on'],order_id=r['id']))
        for r in self.connection.execute('''SELECT p.*,l.name,a.name account FROM loan_payments p JOIN loans l ON l.id=p.loan_id JOIN accounts a ON a.id=p.account_id'''):
            if r['interest_cents']<=0:continue
            result.append(dict(id=f'loan:{r["id"]}',origin='loan',source_id=r['loan_id'],spent_on=r['paid_on'],concept='Intereses · '+r['name'],category='Intereses de préstamos',category_key='loan_interest',amount_cents=r['interest_cents'],paid=True,paid_on=r['paid_on'],account_id=r['account_id'],account=r['account'],due_on=None,cancelled=bool(r['cancelled_at']),estimated=False,detail='Automático desde Préstamos',created_at=r['created_at'],order_id=r['id']))
        for r in self.connection.execute("SELECT e.*,a.name,c.account_id FROM credit_card_charges e JOIN credit_cards c ON c.id=e.card_id JOIN accounts a ON a.id=c.account_id"):
            for key,title in [('interest_cents','Intereses de tarjeta'),('fee_cents','Cargos de tarjeta')]:
                if r[key]:result.append(dict(id=f"card:{r['id']}:{key}",origin='card',source_id=r['card_id'],spent_on=r['charged_on'],concept=title+' · '+r['name'],category=title,category_key='card_'+key,amount_cents=r[key],paid=True,paid_on=r['charged_on'],account_id=r['account_id'],account=r['name'],due_on=None,cancelled=bool(r['cancelled_at']),estimated=False,detail='Cargado a tarjeta · deuda y pagos gestionados en Dinero',created_at=r['created_at'],order_id=r['id']))
        return result

    @staticmethod
    def _filter(rows,f):
        if f.date_basis not in ('spent','paid'):raise StorageError('Selecciona fecha del gasto o fecha de pago.')
        day='paid_on' if f.date_basis=='paid' else 'spent_on'
        if f.start and f.end and f.start>f.end:raise StorageError('Revisa el rango de fechas.')
        return sorted([r for r in rows if
            r[day] is not None and (not f.start or r[day]>=str(f.start)) and (not f.end or r[day]<=str(f.end)) and
            (f.method_id is None or r.get('method_id')==f.method_id) and
            (f.account_id is None or r['account_id']==f.account_id) and
            (f.category_key is None or r['category_key']==f.category_key) and
            (f.paid is None or r['paid']==f.paid) and (f.cancelled is None or r['cancelled']==f.cancelled) and
            (not f.query or f.query.casefold() in (r['concept']+' '+r['category']+' '+r.get('platform','')).casefold())],key=lambda r:(r[day],r['created_at'],r['order_id'],r['origin']),reverse=True)

    def commission_methods(self):
        with operation(self.connection):
            rows=self.connection.execute("SELECT method_id,method_name FROM sales ORDER BY id DESC").fetchall()
            names={}
            for row in rows:names.setdefault(row['method_id'],row['method_name'])
            return sorted(names.items(),key=lambda r:r[1].casefold())

    def list_movements(self,filters=ExpenseFilter()):
        with operation(self.connection):return self._filter(self._movements(),filters)

    def summary(self,filters=ExpenseFilter()):
        with operation(self.connection):
            rows=[r for r in self._filter(self._movements(),filters) if not r['cancelled']]
            categories={}
            for row in rows:
                key=row['category_key']
                categories.setdefault(key,dict(key=key,name=row['category'],amount_cents=0))['amount_cents']+=row['amount_cents']
            capital=sum(r['capital_cents'] for r in self.connection.execute('SELECT * FROM loan_payments WHERE cancelled_at IS NULL') if
                (not filters.start or r['paid_on']>=str(filters.start)) and (not filters.end or r['paid_on']<=str(filters.end)) and (filters.account_id is None or r['account_id']==filters.account_id))
            total=sum(r['amount_cents'] for r in rows);paid=sum(r['amount_cents'] for r in rows if r['paid'])
            return dict(total_cents=total,paid_cents=paid,pending_cents=total-paid,loan_capital_cents=capital,
                categories=sorted(categories.values(),key=lambda r:r['amount_cents'],reverse=True),recent=rows[:4],count=len(rows),estimated=any(r['estimated'] for r in rows))
