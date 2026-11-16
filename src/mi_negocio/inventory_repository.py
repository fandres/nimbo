"""Inventario por modelo: apertura explícita y movimientos dentro de la transacción."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from .storage import StorageError, operation


def inventory_state(connection):
    return dict(connection.execute('SELECT * FROM inventory_state WHERE id=1').fetchone())


def available(connection, product_id):
    return connection.execute('SELECT COALESCE(SUM(delta),0) FROM inventory_movements WHERE product_id=?',(product_id,)).fetchone()[0]


def move(connection, product_id, delta, key, kind, reason):
    product=connection.execute('SELECT code,name,kind FROM products WHERE id=?',(product_id,)).fetchone()
    if not product or product['kind']!='product':raise StorageError('Selecciona un producto del catálogo, no un servicio.')
    if available(connection,product_id)+delta<0:
        raise StorageError(f"Stock insuficiente para {product['code']} · {product['name']}. Disponibles: {available(connection,product_id)}.")
    connection.execute('INSERT INTO inventory_movements(product_id,delta,operation_key,kind,reason,code,name,created_at) VALUES(?,?,?,?,?,?,?,?)',
        (product_id,delta,key,kind,reason,product['code'],product['name'],datetime.now(timezone.utc).isoformat()))
    connection.execute('UPDATE inventory_state SET revision=revision+1 WHERE id=1')


def sale_out(connection, sale_id, lines):
    if not inventory_state(connection)['initialized']:return
    quantities=defaultdict(int)
    for line in lines:
        product=connection.execute('SELECT kind FROM products WHERE id=?',(line.product_id,)).fetchone()
        if product and product['kind']=='product':quantities[line.product_id]+=line.quantity
    for key,quantity in quantities.items():move(connection,key,-quantity,f'sale:{sale_id}','sale',f'Venta #{sale_id}')


def cancel_sale(connection, sale_id):
    rows=connection.execute('SELECT product_id,SUM(delta) AS delta FROM inventory_movements WHERE operation_key=? OR operation_key LIKE ? GROUP BY product_id',(f'sale:{sale_id}',f'sale-edit:{sale_id}:%')).fetchall()
    for row in rows:move(connection,row['product_id'],-row['delta'],f'cancel:{sale_id}','cancellation',f'Anulación de venta #{sale_id}')


def receipt_in(connection, receipt_id):
    if not inventory_state(connection)['initialized']:return
    for row in connection.execute('SELECT product_id,SUM(quantity) AS qty FROM receipt_lines WHERE receipt_id=? GROUP BY product_id',(receipt_id,)).fetchall():
        move(connection,row['product_id'],row['qty'],f'receipt:{receipt_id}','receipt',f'Recepción #{receipt_id}')


def reverse_receipt(connection, receipt_id):
    if not inventory_state(connection)['initialized']:return
    if connection.execute('SELECT 1 FROM inventory_baseline_receipts WHERE receipt_id=?',(receipt_id,)).fetchone():
        raise StorageError('Esta recepción forma parte del inventario inicial confirmado. Corrige las existencias mediante un ajuste con motivo desde Inventario.')
    from .fifo_repository import receipt_has_sales
    if receipt_has_sales(connection, receipt_id):
        raise StorageError('Esta recepción respalda ventas vigentes. Corrige o anula esas ventas antes de deshacer la recepción.')
    rows=connection.execute('SELECT product_id,delta FROM inventory_movements WHERE operation_key=?',(f'receipt:{receipt_id}',)).fetchall()
    for row in rows:move(connection,row['product_id'],-row['delta'],f'reverse:{receipt_id}','reversal',f'Reversión de recepción #{receipt_id}')


class InventoryRepository:
    def __init__(self, connection):self.connection=connection

    def state(self):
        with operation(self.connection):return inventory_state(self.connection)

    def _preview(self):
        products=[dict(r) for r in self.connection.execute("SELECT id,code,name,kind,active FROM products ORDER BY id")]
        receipts=[dict(r) for r in self.connection.execute('SELECT r.id,l.product_id,l.quantity FROM purchase_receipts r JOIN receipt_lines l ON l.receipt_id=r.id WHERE r.reversed_at IS NULL ORDER BY r.id,l.id')]
        counts=defaultdict(int)
        for r in receipts:counts[r['product_id']]+=r['quantity']
        token=hashlib.sha256(json.dumps([products,receipts],sort_keys=True).encode()).hexdigest()
        return {'token':token,'rows':[dict(p,received=counts[p['id']]) for p in products if p['kind']=='product']}

    def preview(self):
        with operation(self.connection):return self._preview()

    def initialize(self, mode, counts, *, expected_token):
        with operation(self.connection):
            if inventory_state(self.connection)['initialized']:raise StorageError('El inventario ya está configurado.')
            preview=self._preview()
            if preview['token']!=expected_token:raise StorageError('Cambió el catálogo o las recepciones. Cierra y vuelve a abrir el asistente para revisar las cantidades.')
            if mode not in ('physical','receipts'):raise StorageError('Selecciona cómo iniciar el inventario.')
            if mode=='receipts':counts={r['id']:r['received'] for r in preview['rows']}
            if set(counts)!={r['id'] for r in preview['rows']} or any(type(q) is not int or not 0<=q<=999999999 for q in counts.values()):
                raise StorageError('Confirma una cantidad entera válida para cada modelo, incluidos los ceros.')
            for product_id,qty in counts.items():move(self.connection,product_id,qty,'opening','opening','Existencias físicas confirmadas' if mode=='physical' else 'Inicio desde compras recibidas')
            self.connection.execute('INSERT INTO inventory_baseline_receipts SELECT id FROM purchase_receipts WHERE reversed_at IS NULL')
            self.connection.execute('UPDATE inventory_state SET initialized=1,mode=?,initialized_at=?,revision=revision+1 WHERE id=1',(mode,datetime.now(timezone.utc).isoformat()))

    def rows(self):
        with operation(self.connection):
            state=inventory_state(self.connection)
            rows=[dict(r) for r in self.connection.execute("SELECT id,code,name,active FROM products WHERE kind='product' ORDER BY name,code")]
            for row in rows:
                row['available']=available(self.connection,row['id']) if state['initialized'] else None
                row['received']=self.connection.execute('SELECT COALESCE(SUM(l.quantity),0) FROM receipt_lines l JOIN purchase_receipts r ON r.id=l.receipt_id WHERE r.reversed_at IS NULL AND l.product_id=?',(row['id'],)).fetchone()[0]
                row['sold']=self.connection.execute("SELECT -COALESCE(SUM(delta),0) FROM inventory_movements WHERE product_id=? AND kind IN ('sale','cancellation')",(row['id'],)).fetchone()[0]
                row['in_transit']=self.connection.execute('SELECT COALESCE(SUM(l.quantity),0) FROM purchase_lines l JOIN purchases p ON p.id=l.purchase_id WHERE l.product_id=? AND p.cancelled_at IS NULL AND NOT EXISTS(SELECT 1 FROM purchase_receipts r WHERE r.purchase_id=p.id AND r.reversed_at IS NULL)',(row['id'],)).fetchone()[0]
            return rows

    def history(self, product_id):
        with operation(self.connection):return [dict(r) for r in self.connection.execute('SELECT * FROM inventory_movements WHERE product_id=? ORDER BY id',(product_id,))]

    def set_adjustments_enabled(self, enabled):
        with operation(self.connection):self.connection.execute('UPDATE inventory_state SET adjustments_enabled=?,revision=revision+1 WHERE id=1',(int(bool(enabled)),))

    def adjustment_preview(self, product_id):
        with operation(self.connection):
            state=inventory_state(self.connection)
            if not state['initialized'] or not state['adjustments_enabled']:raise StorageError('Habilita los ajustes en Configuración → Inventario.')
            product=self.connection.execute("SELECT id,code,name FROM products WHERE id=? AND kind='product'",(product_id,)).fetchone()
            if not product:raise StorageError('El producto ya no está disponible para ajustar.')
            return dict(product,available=available(self.connection,product_id),revision=state['revision'])

    def adjust(self, product_id, quantity, reason, *, expected_revision):
        with operation(self.connection):
            state=inventory_state(self.connection)
            if not state['initialized'] or not state['adjustments_enabled']:raise StorageError('Los ajustes de inventario no están habilitados en Configuración.')
            if state['revision']!=expected_revision:raise StorageError('El inventario cambió. Actualiza y revisa de nuevo el ajuste.')
            if type(quantity) is not int or not 0<=quantity<=999999999 or not reason.strip():raise StorageError('Escribe una cantidad válida y el motivo del ajuste.')
            move(self.connection,product_id,quantity-available(self.connection,product_id),f"adjust:{state['revision']}",'adjustment',reason.strip())
