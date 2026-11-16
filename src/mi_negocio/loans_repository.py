"""Capital pendiente e intereses registrados manualmente; sin amortización implícita."""
from .storage import operation, StorageError
from .sales import check_cents
from .expenses import valid_day
from .expenses_repository import check_account,timestamp,payload


class LoansRepository:
    def __init__(self,connection):self.connection=connection

    def _get(self,key):
        row=self.connection.execute('SELECT * FROM loans WHERE id=?',(key,)).fetchone()
        if not row:raise StorageError('El préstamo ya no existe.')
        result=dict(row)
        result['balance_cents']=row['principal_cents']-sum(r[0] for r in self.connection.execute('SELECT capital_cents FROM loan_payments WHERE loan_id=? AND cancelled_at IS NULL',(key,)))
        return result

    def list_loans(self):
        with operation(self.connection):return [self._get(r[0]) for r in self.connection.execute('SELECT id FROM loans ORDER BY id DESC')]

    def _event(self,key,description,data):
        self.connection.execute('INSERT INTO loan_events(loan_id,changed_at,description,snapshot) VALUES(?,?,?,?)',(key,timestamp(),description,payload(data)))

    def save_loan(self,name,opened_on,principal_cents,*,request_id=None,loan_id=None,expected_revision=None):
        check_cents(principal_cents);valid_day(opened_on,'Fecha del saldo inicial')
        if not name.strip() or principal_cents==0:raise StorageError('Escribe la entidad o nombre y un saldo inicial mayor que cero.')
        raw=payload([name.strip(),opened_on,principal_cents])
        with operation(self.connection):
            if loan_id:
                row=self._get(loan_id)
                if row['revision']!=expected_revision:raise StorageError('El préstamo cambió. Actualiza la vista.')
                if self.connection.execute('SELECT 1 FROM loan_payments WHERE loan_id=?',(loan_id,)).fetchone():raise StorageError('El préstamo tiene historial de pagos; no se puede cambiar su saldo inicial.')
                self.connection.execute('UPDATE loans SET name=?,opened_on=?,principal_cents=?,revision=revision+1 WHERE id=?',(name.strip(),str(opened_on),principal_cents,loan_id))
                key=loan_id
            else:
                if not request_id:raise StorageError('Falta la identificación del registro.')
                old=self.connection.execute('SELECT * FROM loans WHERE request_id=?',(request_id,)).fetchone()
                if old:
                    if old['request_payload']!=raw:raise StorageError('La solicitud ya se guardó con otros datos.')
                    return self._get(old['id'])
                key=self.connection.execute('INSERT INTO loans(request_id,request_payload,name,opened_on,principal_cents,created_at) VALUES(?,?,?,?,?,?)',(request_id,raw,name.strip(),str(opened_on),principal_cents,timestamp())).lastrowid
            result=self._get(key);self._event(key,'Saldo inicial',result);return result

    def pay(self,loan_id,paid_on,account_id,capital_cents,interest_cents,*,request_id,note=''):
        check_cents(capital_cents);check_cents(interest_cents);check_cents(capital_cents+interest_cents);valid_day(paid_on,'Fecha de pago')
        if not request_id or capital_cents+interest_cents<=0:raise StorageError('Ingresa capital o intereses mayores que cero.')
        raw=payload([loan_id,paid_on,account_id,capital_cents,interest_cents,note.strip()])
        with operation(self.connection):
            old=self.connection.execute('SELECT * FROM loan_payments WHERE request_id=?',(request_id,)).fetchone()
            if old:
                if old['request_payload']!=raw:raise StorageError('La solicitud ya se guardó con otros datos.')
                return dict(old)
            loan=self._get(loan_id)
            if str(paid_on)<loan['opened_on']:raise StorageError('El pago debe ser igual o posterior a la fecha del saldo inicial.')
            if capital_cents>loan['balance_cents']:raise StorageError('El abono a capital supera el saldo pendiente.')
            check_account(self.connection,account_id)
            key=self.connection.execute('INSERT INTO loan_payments(request_id,request_payload,loan_id,paid_on,account_id,capital_cents,interest_cents,note,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(request_id,raw,loan_id,str(paid_on),account_id,capital_cents,interest_cents,note.strip(),timestamp())).lastrowid
            self.connection.execute('UPDATE loans SET revision=revision+1 WHERE id=?',(loan_id,))
            result=dict(self.connection.execute('SELECT * FROM loan_payments WHERE id=?',(key,)).fetchone())
            self._event(loan_id,'Pago registrado',result);return result

    def payments(self,loan_id):
        with operation(self.connection):return [dict(r) for r in self.connection.execute('SELECT p.*,a.name account FROM loan_payments p JOIN accounts a ON a.id=p.account_id WHERE loan_id=? ORDER BY paid_on DESC,p.id DESC',(loan_id,))]

    def cancel_payment(self,key,reason):
        if not reason.strip():raise StorageError('Escribe el motivo de anulación.')
        with operation(self.connection):
            row=self.connection.execute('SELECT * FROM loan_payments WHERE id=?',(key,)).fetchone()
            if not row or row['cancelled_at']:raise StorageError('El pago ya no existe o ya fue anulado.')
            self.connection.execute('UPDATE loan_payments SET cancelled_at=?,cancellation_reason=? WHERE id=?',(timestamp(),reason.strip(),key))
            self.connection.execute('UPDATE loans SET revision=revision+1 WHERE id=?',(row['loan_id'],))
            updated=dict(self.connection.execute('SELECT * FROM loan_payments WHERE id=?',(key,)).fetchone())
            self._event(row['loan_id'],'Pago anulado',updated)

    def history(self,loan_id):
        with operation(self.connection):return [dict(r) for r in self.connection.execute('SELECT * FROM loan_events WHERE loan_id=? ORDER BY id',(loan_id,))]
