"""Recepciones completas; entradas históricas, todavía sin salidas de ventas."""
from datetime import date
from .storage import operation, StorageError


def receipt_record(connection, row):
    if row is None:return None
    result=dict(row)
    result['lines']=[dict(line) for line in connection.execute('SELECT * FROM receipt_lines WHERE receipt_id=? ORDER BY id',(row['id'],))]
    return result


def current_receipt(connection,purchase_id):
    return receipt_record(connection,connection.execute('SELECT * FROM purchase_receipts WHERE purchase_id=? AND reversed_at IS NULL',(purchase_id,)).fetchone())


class PurchaseReceiptsRepository:
    def __init__(self,connection):self.connection=connection

    def current(self,purchase_id):
        with operation(self.connection):return current_receipt(self.connection,purchase_id)

    def history(self,purchase_id):
        with operation(self.connection):
            return [receipt_record(self.connection,row) for row in self.connection.execute('SELECT * FROM purchase_receipts WHERE purchase_id=? ORDER BY id',(purchase_id,))]

    def receive(self,purchase_id,received_on,*,expected_revision):
        from .purchases_repository import PurchasesRepository,now
        with operation(self.connection):
            purchases=PurchasesRepository(self.connection)
            previous=purchases._get(purchase_id)
            if previous['cancelled_at']:raise StorageError('No se puede recibir una compra anulada.')
            if type(received_on) is not date or not date.fromisoformat(previous['purchased_on'])<=received_on<=date.today():
                raise StorageError('La recepción debe estar entre la fecha de compra y hoy.')
            existing=current_receipt(self.connection,purchase_id)
            if existing:
                if existing['received_on']==received_on.isoformat():return existing
                raise StorageError('El pedido ya fue recibido. Deshaz la recepción para corregir su fecha.')
            purchases._editable(purchase_id,expected_revision)
            purchases._snapshot(previous)
            timestamp=now()
            cursor=self.connection.execute('INSERT INTO purchase_receipts(purchase_id,received_on,created_at) VALUES(?,?,?)',
                (purchase_id,received_on.isoformat(),timestamp))
            for line in previous['lines']:
                self.connection.execute('INSERT INTO receipt_lines(receipt_id,purchase_line_id,product_id,code,name,quantity) VALUES(?,?,?,?,?,?)',
                    (cursor.lastrowid,line['id'],line['product_id'],line['code'],line['name'],line['quantity']))
            self.connection.execute('UPDATE purchases SET revision=revision+1,updated_at=? WHERE id=?',(timestamp,purchase_id))
            from .inventory_repository import receipt_in
            receipt_in(self.connection,cursor.lastrowid)
            return current_receipt(self.connection,purchase_id)

    def reverse(self,receipt_id,reason,*,expected_revision):
        from .purchases_repository import PurchasesRepository,now
        if not reason.strip():raise StorageError('Escribe el motivo para deshacer la recepción.')
        with operation(self.connection):
            row=self.connection.execute('SELECT * FROM purchase_receipts WHERE id=?',(receipt_id,)).fetchone()
            if row is None:raise StorageError('La recepción no existe.')
            if row['reversed_at']:raise StorageError('Esta recepción ya se deshizo.')
            purchases=PurchasesRepository(self.connection)
            previous=purchases._editable(row['purchase_id'],expected_revision)
            from .inventory_repository import reverse_receipt
            reverse_receipt(self.connection,receipt_id)
            purchases._snapshot(previous);timestamp=now()
            self.connection.execute('UPDATE purchase_receipts SET reversed_at=?,reversal_reason=? WHERE id=?',(timestamp,reason.strip(),receipt_id))
            self.connection.execute('UPDATE purchases SET revision=revision+1,updated_at=? WHERE id=?',(timestamp,row['purchase_id']))
            return receipt_record(self.connection,self.connection.execute('SELECT * FROM purchase_receipts WHERE id=?',(receipt_id,)).fetchone())
