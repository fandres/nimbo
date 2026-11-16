"""Persistencia atómica del catálogo en un archivo SQLite local."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .catalog import Product, ValidatedProduct


from .storage import StorageError, DuplicateCodeError
from .database import open_database


class CatalogRepository:
    def __init__(self, path: Path):
        self.connection = open_database(path)

    @contextmanager
    def _operation(self):
        try:
            with self.connection:
                yield
        except sqlite3.IntegrityError as error:
            if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                raise DuplicateCodeError('Este código ya existe. Usa otro o edita el registro existente.') from error
            raise StorageError('Los datos no cumplen las reglas del catálogo.') from error
        except sqlite3.Error as error:
            raise StorageError('No se pudo acceder al catálogo. Revisa permisos y espacio disponible; si está ocupado, vuelve a intentarlo.') from error

    def code_exists(self, code: str, exclude_id: int | None = None) -> bool:
        """Check exact catalog codes, including inactive records."""
        with self._operation():
            return self.connection.execute(
                'SELECT 1 FROM products WHERE code=? AND (? IS NULL OR id<>?) LIMIT 1',
                (code, exclude_id, exclude_id),
            ).fetchone() is not None

    @staticmethod
    def _product(row) -> Product:
        values = dict(row)
        values.pop('brand_id', None)
        values.pop('subtype_id', None)
        values['active'] = bool(values['active'])
        return Product(**values)

    @staticmethod
    def _values(data: ValidatedProduct) -> tuple:
        return data.code, data.name, data.kind, data.price_cop_cents, int(data.active)

    SELECT_PRODUCTS = """SELECT p.*, COALESCE(b.name, '') AS brand, COALESCE(s.name, '') AS subtype
        FROM products p LEFT JOIN catalog_options b ON p.brand_id=b.id
        LEFT JOIN catalog_options s ON p.subtype_id=s.id"""

    @staticmethod
    def _check_group(group):
        if group not in ('brand', 'subtype'):
            raise StorageError('Lista no válida.')

    def _option_id(self, group: str, name: str):
        self._check_group(group)
        name = name.strip()
        if not name:
            return None
        self.connection.execute('INSERT INTO catalog_options(group_key,name,name_key) VALUES (?,?,?) ON CONFLICT(group_key,name_key) DO NOTHING', (group, name, name.casefold()))
        return self.connection.execute('SELECT id FROM catalog_options WHERE group_key=? AND name_key=?', (group, name.casefold())).fetchone()[0]

    def list_options(self, group: str) -> list[str]:
        self._check_group(group)
        with self._operation():
            return [row[0] for row in self.connection.execute('SELECT name FROM catalog_options WHERE group_key=? ORDER BY name_key', (group,))]

    def add_option(self, group: str, name: str) -> None:
        if not name.strip():
            raise StorageError('Escribe un nombre para la lista.')
        with self._operation():
            self._option_id(group, name)

    def rename_option(self, group: str, old_name: str, new_name: str) -> None:
        self._check_group(group)
        new_name = new_name.strip()
        if not new_name:
            raise StorageError('Escribe un nombre para la lista.')
        with self._operation():
            self.connection.execute('BEGIN IMMEDIATE')
            conflict = self.connection.execute('SELECT id FROM catalog_options WHERE group_key=? AND name_key=? AND name_key<>?', (group, new_name.casefold(), old_name.casefold())).fetchone()
            if conflict:
                raise StorageError('Ya existe una opción con ese nombre.')
            cursor = self.connection.execute('UPDATE catalog_options SET name=?,name_key=? WHERE group_key=? AND name_key=?', (new_name, new_name.casefold(), group, old_name.casefold()))
            if cursor.rowcount != 1:
                raise StorageError('La opción ya no existe. Vuelve a abrir la lista.')

    def create(self, data: ValidatedProduct) -> Product:
        now = datetime.now(timezone.utc).isoformat()
        with self._operation():
            brand_id = self._option_id('brand', data.brand)
            subtype_id = self._option_id('subtype', data.subtype)
            cursor = self.connection.execute(
                'INSERT INTO products (code,name,kind,price_cop_cents,active,created_at,updated_at,brand_id,subtype_id) VALUES (?,?,?,?,?,?,?,?,?)',
                (*self._values(data), now, now, brand_id, subtype_id),
            )
            row = self.connection.execute(self.SELECT_PRODUCTS + ' WHERE p.id=?', (cursor.lastrowid,)).fetchone()
        return self._product(row)

    def update(self, product_id: int, data: ValidatedProduct) -> Product:
        with self._operation():
            self.connection.execute('BEGIN IMMEDIATE')
            previous=self.connection.execute('SELECT kind FROM products WHERE id=?',(product_id,)).fetchone()
            if previous and previous['kind']!=data.kind and self.connection.execute('SELECT 1 FROM inventory_movements WHERE product_id=? LIMIT 1',(product_id,)).fetchone():
                raise StorageError('No puedes cambiar entre producto y servicio si el modelo tiene movimientos de inventario.')
            brand_id = self._option_id('brand', data.brand)
            subtype_id = self._option_id('subtype', data.subtype)
            cursor = self.connection.execute(
                'UPDATE products SET code=?,name=?,kind=?,price_cop_cents=?,active=?,updated_at=?,brand_id=?,subtype_id=? WHERE id=?',
                (*self._values(data), datetime.now(timezone.utc).isoformat(), brand_id, subtype_id, product_id),
            )
            if cursor.rowcount != 1:
                raise StorageError('El registro ya no existe. Actualiza el catálogo.')
            row = self.connection.execute(self.SELECT_PRODUCTS + ' WHERE p.id=?', (product_id,)).fetchone()
        return self._product(row)

    def list_products(self, query: str = '', kind: str | None = None, active: bool | None = None, brand: str | None = None, subtype: str | None = None) -> list[Product]:
        clauses, parameters = [], []
        if query:
            clauses.append('(instr(casefold(p.code), ?) > 0 OR instr(casefold(p.name), ?) > 0)')
            parameters.extend([query.casefold(), query.casefold()])
        if kind is not None:
            clauses.append('kind=?')
            parameters.append(kind)
        if active is not None:
            clauses.append('active=?')
            parameters.append(int(active))

        for column, value in [('b.name', brand), ('s.name', subtype)]:
            if value is not None:
                clauses.append(f'{column}=?')
                parameters.append(value)
        sql = self.SELECT_PRODUCTS
        if clauses:
            sql += ' WHERE ' + ' AND '.join(clauses)
        sql += ' ORDER BY casefold(p.name), code'
        with self._operation():
            rows = self.connection.execute(sql, parameters).fetchall()
        return [self._product(row) for row in rows]

    def set_active(self, product_id: int, active: bool) -> None:
        with self._operation():
            cursor = self.connection.execute('UPDATE products SET active=?,updated_at=? WHERE id=?',
                                             (int(active), datetime.now(timezone.utc).isoformat(), product_id))
            if cursor.rowcount != 1:
                raise StorageError('El registro ya no existe. Actualiza el catálogo.')

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
