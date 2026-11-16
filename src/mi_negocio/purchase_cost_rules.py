"""Cost applicability; absent rule inherits, an empty selection excludes all costs."""
import json
from .purchase_concepts import PurchaseConceptsRepository
from .storage import operation, StorageError


class PurchaseCostRules:
    def __init__(self, connection):
        self.connection = connection

    def _target(self, scope):
        if scope not in ('subtype', 'product'):
            raise StorageError('Selecciona subtipo o producto.')
        return 'purchase_cost_rules_' + scope

    def selection(self, scope, target_id):
        row = self.connection.execute(
            'SELECT concepts FROM '+self._target(scope)+' WHERE target_id=?', (target_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, scope, target_id, selection):
        table = self._target(scope)
        with operation(self.connection):
            sql = ("SELECT 1 FROM products WHERE id=? AND kind='product'" if scope == 'product'
                   else "SELECT 1 FROM catalog_options WHERE id=? AND group_key='subtype'")
            if not self.connection.execute(sql, (target_id,)).fetchone():
                raise StorageError('El producto o subtipo ya no existe.')
            if selection is None:
                self.connection.execute('DELETE FROM '+table+' WHERE target_id=?', (target_id,))
                return
            available = {r['key'] for r in PurchaseConceptsRepository(self.connection).list()}
            if not set(selection) <= available:
                raise StorageError('Actualiza la lista de conceptos antes de guardar.')
            self.connection.execute('INSERT INTO '+table+' VALUES(?,?) ON CONFLICT(target_id) DO UPDATE SET concepts=excluded.concepts',
                                    (target_id, json.dumps(sorted(set(selection)))))

    def inherited(self, product_id):
        row = self.connection.execute('SELECT subtype_id FROM products WHERE id=?', (product_id,)).fetchone()
        if row and row[0] is not None:
            selection = self.selection('subtype', row[0])
            if selection is not None:
                return selection
        return list(PurchaseConceptsRepository(self.connection).definitions())

    def definitions(self, product_ids):
        keys = set()
        for product_id in set(product_ids):
            selection = self.selection('product', product_id)
            keys.update(self.inherited(product_id) if selection is None else selection)
        return {key: value for key, value in PurchaseConceptsRepository(self.connection).definitions().items() if key in keys}


def migrate_purchase_cost_rules(connection):
    for scope, target in [('subtype', 'catalog_options'), ('product', 'products')]:
        connection.execute('CREATE TABLE IF NOT EXISTS purchase_cost_rules_'+scope+'('
                           'target_id INTEGER PRIMARY KEY REFERENCES '+target+'(id) ON DELETE CASCADE,'
                           'concepts TEXT NOT NULL)')
    connection.execute('PRAGMA user_version=25')
