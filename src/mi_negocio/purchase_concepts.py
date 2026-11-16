"""Conceptos configurables de compras; claves estables e historial preservado."""
import json
from uuid import uuid4
from .storage import operation,StorageError
from .purchases import CATEGORIES

GROUPS={'shipping':'Envío e importación','other':'Impuestos y otros'}


def default_definitions():
    return {key:{'name':name,'group':'shipping' if key in ('international_shipping','importation') else 'other'} for key,name in CATEGORIES.items()}


class PurchaseConceptsRepository:
    def __init__(self,connection):self.connection=connection
    def list(self):
        return [dict(row) for row in self.connection.execute('SELECT * FROM purchase_concepts ORDER BY position,key')]
    def definitions(self):
        return {r['key']:{'name':r['name'],'group':r['summary_group']} for r in self.list() if r['enabled']}
    def save(self,name,group,*,key=None,enabled=True):
        name=' '.join(name.split())
        if not name or len(name)>100:raise StorageError('Escribe un nombre de hasta 100 caracteres.')
        if group not in GROUPS:raise StorageError('Selecciona el grupo del resumen.')
        with operation(self.connection):
            if self.connection.execute('SELECT 1 FROM purchase_concepts WHERE name_key=? AND key!=?',(name.casefold(),key or '')).fetchone():raise StorageError('Ya existe un concepto con ese nombre.')
            if key:
                if not self.connection.execute('SELECT 1 FROM purchase_concepts WHERE key=?',(key,)).fetchone():raise StorageError('El concepto ya no existe. Actualiza la lista.')
                self.connection.execute('UPDATE purchase_concepts SET name=?,name_key=?,summary_group=?,enabled=? WHERE key=?',(name,name.casefold(),group,int(enabled),key))
            else:
                key='custom_'+uuid4().hex
                self.connection.execute('INSERT INTO purchase_concepts(key,name,name_key,summary_group,enabled,position) VALUES(?,?,?,?,?,(SELECT COALESCE(MAX(position),0)+1 FROM purchase_concepts))',(key,name,name.casefold(),group,int(enabled)))
            return dict(self.connection.execute('SELECT * FROM purchase_concepts WHERE key=?',(key,)).fetchone())
    def remove(self,key):
        with operation(self.connection):
            used=self.connection.execute('SELECT 1 FROM purchase_costs WHERE category=? LIMIT 1',(key,)).fetchone()
            # A pending or No aplica concept is also part of an existing order.
            used=used or any(key in json.loads(r[0] or '{}') for r in self.connection.execute('SELECT cost_states_json FROM purchases'))
            used=used or any(key in json.loads(r[0]).get('cost_states',{}) for r in self.connection.execute('SELECT snapshot FROM purchase_revisions') if json.loads(r[0]).get('cost_states'))
            if used or key in CATEGORIES:
                self.connection.execute('UPDATE purchase_concepts SET enabled=0 WHERE key=?',(key,));return 'disabled'
            self.connection.execute('DELETE FROM purchase_concepts WHERE key=?',(key,));return 'deleted'


def migrate_purchase_concepts(c):
    c.execute('CREATE TABLE IF NOT EXISTS purchase_concepts(key TEXT PRIMARY KEY,name TEXT NOT NULL,name_key TEXT NOT NULL UNIQUE,summary_group TEXT NOT NULL CHECK(summary_group IN (\'shipping\',\'other\')),enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),position INTEGER NOT NULL)')
    for i,(key,data) in enumerate(default_definitions().items()):
        c.execute('INSERT OR IGNORE INTO purchase_concepts VALUES(?,?,?,?,1,?)',(key,data['name'],data['name'].casefold(),data['group'],i))
    for table,column in (('purchases','cost_definitions_json'),('purchase_lines','extra_allocations_json')):
        if column not in {r[1] for r in c.execute('PRAGMA table_info('+table+')')}:
            c.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' TEXT')
    # Keep existing IDs and values; only remove the old four-concept CHECK.
    c.execute('''CREATE TABLE purchase_costs_flexible(
        id INTEGER PRIMARY KEY,purchase_id INTEGER NOT NULL REFERENCES purchases(id),
        category TEXT NOT NULL,description TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents>=0),
        currency TEXT NOT NULL CHECK(currency IN ('COP','USD')),exchange_rate TEXT,converted_on TEXT,
        subtotal_cents INTEGER NOT NULL CHECK(typeof(subtotal_cents)='integer' AND subtotal_cents>=0))''')
    c.execute('INSERT INTO purchase_costs_flexible SELECT * FROM purchase_costs')
    c.execute('DROP TABLE purchase_costs');c.execute('ALTER TABLE purchase_costs_flexible RENAME TO purchase_costs')
    c.execute('CREATE INDEX purchase_costs_parent ON purchase_costs(purchase_id)')
    c.execute('PRAGMA user_version=16')
