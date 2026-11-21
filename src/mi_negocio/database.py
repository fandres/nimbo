"""Apertura y migraciones locales con respaldo previo."""
from pathlib import Path
from uuid import uuid4
import sqlite3
from contextlib import closing
from .storage import StorageError
from .expenses_schema import migrate_expenses
from .money_schema import migrate_money


def backup_database(connection, path):
    target = path.with_name(path.name + '.backup-' + uuid4().hex)
    with closing(sqlite3.connect(target)) as backup:
        connection.backup(backup)


def migrate_catalog(connection, version):
    if version == 0:
        connection.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL COLLATE BINARY UNIQUE CHECK(length(trim(code)) > 0),
            name TEXT NOT NULL CHECK(length(trim(name)) > 0),
            kind TEXT NOT NULL CHECK(kind IN ('product', 'service')),
            price_cop_cents INTEGER NOT NULL CHECK(typeof(price_cop_cents) = 'integer' AND price_cop_cents >= 0),
            active INTEGER NOT NULL CHECK(active IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        connection.execute('PRAGMA user_version=1')
    if version < 2:
        # Explicit transaction also covers DDL: no partial migration on failure.
        connection.execute("""CREATE TABLE catalog_options (
            id INTEGER PRIMARY KEY, group_key TEXT NOT NULL CHECK(group_key IN ('brand','subtype')),
            name TEXT NOT NULL CHECK(length(trim(name)) > 0), name_key TEXT NOT NULL,
            UNIQUE(group_key, name_key))""")
        connection.execute('ALTER TABLE products ADD COLUMN brand_id INTEGER REFERENCES catalog_options(id)')
        connection.execute('ALTER TABLE products ADD COLUMN subtype_id INTEGER REFERENCES catalog_options(id)')
        connection.execute('PRAGMA user_version=2')

def migrate_sales(connection):
    statements = [
        '''CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)))''',
        '''CREATE TABLE payment_methods(id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE, provider TEXT NOT NULL,
            rate_percent TEXT NOT NULL, fixed_cents INTEGER NOT NULL CHECK(typeof(fixed_cents)='integer' AND fixed_cents>=0),
            enabled INTEGER NOT NULL CHECK(enabled IN(0,1)), placement TEXT NOT NULL CHECK(placement IN('primary','additional')),
            default_received INTEGER NOT NULL CHECK(default_received IN(0,1)))''',
        '''CREATE TABLE sales(id INTEGER PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, request_payload TEXT NOT NULL,
            sold_on TEXT NOT NULL, invoice_ref TEXT NOT NULL, method_id INTEGER NOT NULL REFERENCES payment_methods(id),
            method_name TEXT NOT NULL, provider TEXT NOT NULL, rate_percent TEXT NOT NULL, fixed_cents INTEGER NOT NULL,
            destination_account_id INTEGER NOT NULL REFERENCES accounts(id), shipping_enabled INTEGER NOT NULL CHECK(shipping_enabled IN(0,1)),
            shipping_charged_cents INTEGER NOT NULL CHECK(typeof(shipping_charged_cents)='integer' AND shipping_charged_cents>=0),
            shipping_cost_cents INTEGER NOT NULL CHECK(typeof(shipping_cost_cents)='integer' AND shipping_cost_cents>=0),
            subtotal_cents INTEGER NOT NULL CHECK(typeof(subtotal_cents)='integer' AND subtotal_cents>=0),
            total_cents INTEGER NOT NULL CHECK(typeof(total_cents)='integer' AND total_cents>=0),
            commission_cents INTEGER NOT NULL CHECK(typeof(commission_cents)='integer' AND commission_cents BETWEEN 0 AND total_cents))''',
        '''CREATE TABLE sale_lines(id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id), product_id INTEGER NOT NULL REFERENCES products(id),
            code TEXT NOT NULL, name TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(typeof(quantity)='integer' AND quantity>0),
            unit_price_cents INTEGER NOT NULL CHECK(typeof(unit_price_cents)='integer' AND unit_price_cents>=0))''',
        '''CREATE TABLE receipts(sale_id INTEGER PRIMARY KEY REFERENCES sales(id), received_on TEXT NOT NULL,
            account_id INTEGER NOT NULL REFERENCES accounts(id), commission_cents INTEGER NOT NULL CHECK(typeof(commission_cents)='integer' AND commission_cents>=0))''',
        '''CREATE TABLE shipping_payments(sale_id INTEGER PRIMARY KEY REFERENCES sales(id), paid_on TEXT NOT NULL, account_id INTEGER NOT NULL REFERENCES accounts(id))''',
    ]
    for statement in statements:
        connection.execute(statement)
    connection.executemany('INSERT INTO accounts(name,name_key,enabled) VALUES (?,?,1)', [('Efectivo','efectivo'),('Cuenta principal','cuenta principal')])
    connection.executemany('INSERT INTO payment_methods(name,name_key,provider,rate_percent,fixed_cents,enabled,placement,default_received) VALUES (?,?,?,?,?,1,?,?)', [
        ('Efectivo','efectivo','','0',0,'primary',1),
        ('Transferencia','transferencia','','0',0,'primary',1),
        ('Tarjeta','tarjeta','Bolt','3.59',90000,'primary',0),
        ('Addi','addi','Addi','7.735',0,'additional',0)])
    connection.execute('PRAGMA user_version=3')


def open_database(path: Path):
    connection = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing_data = path.exists() and path.stat().st_size > 0
        connection = sqlite3.connect(path, timeout=1)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.create_function('casefold',1,str.casefold,deterministic=True)
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        if version > 29:
            raise StorageError('Esta base pertenece a una versión más reciente. Actualiza la aplicación.')
        if version < 29:
            if existing_data:
                backup_database(connection,path)
            # One outer transaction covers every migration, including old catalog schemas.
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                if version < 3:
                    migrate_catalog(connection,version)
                    migrate_sales(connection)
                if version < 4:
                    connection.execute("ALTER TABLE accounts ADD COLUMN kind TEXT NOT NULL DEFAULT 'bank' CHECK(kind IN ('cash','bank'))")
                    connection.execute("ALTER TABLE accounts ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0 CHECK(is_default IN (0,1))")
                    connection.execute("ALTER TABLE payment_methods ADD COLUMN account_kind TEXT NOT NULL DEFAULT 'any' CHECK(account_kind IN ('any','cash','bank'))")
                    # IDs 1 and 2 are the original seeded cash/transfer entries, even after renaming.
                    connection.execute("UPDATE accounts SET kind='cash',is_default=1 WHERE id=1")
                    connection.execute("UPDATE payment_methods SET account_kind='cash' WHERE id=1")
                    connection.execute("UPDATE payment_methods SET account_kind='bank' WHERE id=2")
                    connection.execute('PRAGMA user_version=4')
                if version < 5:
                    connection.execute("CREATE TABLE carriers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,name_key TEXT NOT NULL UNIQUE,enabled INTEGER NOT NULL CHECK(enabled IN (0,1)))")
                    connection.executemany('INSERT INTO carriers(name,name_key,enabled) VALUES(?,?,1)', [('Inter Rapidísimo','inter rapidísimo'),('Servientrega','servientrega')])
                    connection.execute("ALTER TABLE sales ADD COLUMN customer_name TEXT NOT NULL DEFAULT ''")
                    connection.execute("ALTER TABLE sales ADD COLUMN carrier_id INTEGER REFERENCES carriers(id)")
                    connection.execute("ALTER TABLE sales ADD COLUMN carrier_name TEXT NOT NULL DEFAULT ''")
                    connection.execute("ALTER TABLE sales ADD COLUMN destination_city TEXT NOT NULL DEFAULT ''")
                    connection.execute("ALTER TABLE sales ADD COLUMN has_withholding INTEGER NOT NULL DEFAULT 0 CHECK(has_withholding IN (0,1))")
                    connection.execute('PRAGMA user_version=5')
                if version < 6:
                    connection.execute("ALTER TABLE sales ADD COLUMN tracking_number TEXT NOT NULL DEFAULT ''")
                    connection.execute('PRAGMA user_version=6')
                if version < 7:
                    connection.execute("CREATE TABLE shipping_payments_new(sale_id INTEGER PRIMARY KEY REFERENCES sales(id), paid_on TEXT NOT NULL, account_id INTEGER REFERENCES accounts(id), payment_kind TEXT NOT NULL DEFAULT 'account' CHECK(payment_kind IN ('unspecified','account','debit_card','credit_card')))")
                    connection.execute("INSERT INTO shipping_payments_new(sale_id,paid_on,account_id) SELECT sale_id,paid_on,account_id FROM shipping_payments")
                    connection.execute('DROP TABLE shipping_payments')
                    connection.execute('ALTER TABLE shipping_payments_new RENAME TO shipping_payments')
                    connection.execute("ALTER TABLE sales ADD COLUMN customer_identification TEXT NOT NULL DEFAULT ''")
                    connection.execute("ALTER TABLE sales ADD COLUMN customer_email TEXT NOT NULL DEFAULT ''")
                    connection.execute('PRAGMA user_version=7')
                if version < 8:
                    connection.execute("ALTER TABLE sales ADD COLUMN cancelled_at TEXT")
                    connection.execute("ALTER TABLE sales ADD COLUMN cancellation_reason TEXT NOT NULL DEFAULT ''")
                    connection.execute('PRAGMA user_version=8')
                if version < 9:
                    migrate_purchases(connection)
                if version < 10:
                    migrate_purchase_allocations(connection)
                if version < 11:
                    migrate_purchase_receipts(connection)
                if version < 12:
                    migrate_inventory(connection)
                if version < 13:
                    migrate_expenses(connection)
                if version < 14:
                    migrate_money(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 14:
                    migrate_purchase_totals(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 15:
                    from .purchase_concepts import migrate_purchase_concepts
                    migrate_purchase_concepts(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 16:
                    migrate_supplier_alias(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 17:
                    migrate_purchase_tracking(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 18:
                    from .attachments import migrate_attachments
                    migrate_attachments(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 19:
                    if 'tiers_json' not in {r[1] for r in connection.execute('PRAGMA table_info(payment_methods)')}:
                        connection.execute("ALTER TABLE payment_methods ADD COLUMN tiers_json TEXT NOT NULL DEFAULT '[]'")
                    connection.execute('PRAGMA user_version=20')
                if connection.execute('PRAGMA user_version').fetchone()[0] == 20:
                    from .vat import migrate_vat
                    migrate_vat(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 21:
                    from .withholding import migrate_withholding
                    migrate_withholding(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 22:
                    columns={r[1] for r in connection.execute('PRAGMA table_info(sales)')}
                    for name in ('customer_alias','customer_phone'):
                        if name not in columns:
                            connection.execute(f"ALTER TABLE sales ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
                    connection.execute('PRAGMA user_version=23')
                if connection.execute('PRAGMA user_version').fetchone()[0] == 23:
                    connection.execute("CREATE TABLE IF NOT EXISTS sale_permissions(action TEXT PRIMARY KEY,enabled INTEGER NOT NULL)")
                    for action,enabled in [('edit',1),('cancel',1),('delete',0)]:
                        connection.execute('INSERT OR IGNORE INTO sale_permissions VALUES(?,?)',(action,enabled))
                    connection.execute("CREATE TABLE IF NOT EXISTS sale_id_sequence(id INTEGER PRIMARY KEY CHECK(id=1),last_id INTEGER NOT NULL)")
                    connection.execute("INSERT OR IGNORE INTO sale_id_sequence SELECT 1,COALESCE(MAX(id),0) FROM sales")
                    connection.execute("CREATE TABLE IF NOT EXISTS sale_revisions(id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id),created_at TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL)")
                    columns={r[1] for r in connection.execute('PRAGMA table_info(sales)')}
                    if 'stock_tracked' not in columns:
                        connection.execute("ALTER TABLE sales ADD COLUMN stock_tracked INTEGER NOT NULL DEFAULT 0")
                        connection.execute("UPDATE sales SET stock_tracked=1 WHERE EXISTS(SELECT 1 FROM inventory_movements WHERE operation_key='sale:'||sales.id)")
                    connection.execute('PRAGMA user_version=24')
                if connection.execute('PRAGMA user_version').fetchone()[0] == 24:
                    from .purchase_cost_rules import migrate_purchase_cost_rules
                    migrate_purchase_cost_rules(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 25:
                    columns = {r[1] for r in connection.execute('PRAGMA table_info(purchases)')}
                    for name, declaration in [('invoice_vat_enabled', 'INTEGER NOT NULL DEFAULT 0'),
                                              ('invoice_vat_rate', "TEXT NOT NULL DEFAULT '19'")]:
                        if name not in columns:
                            connection.execute(f'ALTER TABLE purchases ADD COLUMN {name} {declaration}')
                    connection.execute('PRAGMA user_version=26')
                if connection.execute('PRAGMA user_version').fetchone()[0] == 26:
                    from .retention_certificates import migrate_certificates
                    migrate_certificates(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 27:
                    from .retention_certificates import migrate_certificate_documents
                    migrate_certificate_documents(connection)
                if connection.execute('PRAGMA user_version').fetchone()[0] == 28:
                    from .quick_entries import migrate_quick_entries
                    migrate_quick_entries(connection)
        connection.execute('SELECT id,code FROM products LIMIT 0')
        return connection
    except (OSError, sqlite3.Error, StorageError) as error:
        if connection is not None: connection.close()
        if isinstance(error,StorageError): raise
        raise StorageError('No se pudo abrir o actualizar la base. Revisa permisos y espacio disponible.') from error


def migrate_purchases(connection):
    connection.execute("""CREATE TABLE purchases(
        id INTEGER PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, request_payload TEXT NOT NULL,
        purchased_on TEXT NOT NULL, supplier TEXT NOT NULL CHECK(length(trim(supplier))>0),
        reference TEXT NOT NULL, costs_complete INTEGER NOT NULL CHECK(costs_complete IN(0,1)),
        revision INTEGER NOT NULL CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        cancelled_at TEXT, cancellation_reason TEXT NOT NULL DEFAULT '')""")
    common = """currency TEXT NOT NULL CHECK(currency IN('COP','USD')), exchange_rate TEXT,
        converted_on TEXT, subtotal_cents INTEGER NOT NULL CHECK(typeof(subtotal_cents)='integer' AND subtotal_cents>=0)"""
    connection.execute("""CREATE TABLE purchase_lines(
        id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_id INTEGER NOT NULL REFERENCES purchases(id),
        product_id INTEGER NOT NULL REFERENCES products(id), code TEXT NOT NULL, name TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(typeof(quantity)='integer' AND quantity>0),
        unit_cost_cents INTEGER NOT NULL CHECK(typeof(unit_cost_cents)='integer' AND unit_cost_cents>=0), """ + common + ')')
    connection.execute("""CREATE TABLE purchase_costs(
        id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id),
        category TEXT NOT NULL CHECK(category IN('international_shipping','importation','taxes','other')),
        description TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents>=0), """ + common + ')')
    connection.execute("""CREATE TABLE purchase_revisions(
        id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id),
        revision INTEGER NOT NULL, changed_at TEXT NOT NULL, snapshot TEXT NOT NULL,
        UNIQUE(purchase_id,revision))""")
    connection.execute('CREATE INDEX purchase_lines_parent ON purchase_lines(purchase_id)')
    connection.execute('CREATE INDEX purchase_costs_parent ON purchase_costs(purchase_id)')
    connection.execute('PRAGMA user_version=9')


def migrate_purchase_allocations(connection):
    from .purchase_allocation import ALLOCATION_FIELDS
    for field in ALLOCATION_FIELDS.values():
        connection.execute(f"ALTER TABLE purchase_lines ADD COLUMN {field} INTEGER NOT NULL DEFAULT 0 CHECK(typeof({field})='integer' AND {field}>=0)")
    connection.execute('ALTER TABLE purchases ADD COLUMN cost_states_json TEXT')
    connection.execute('PRAGMA user_version=10')


def migrate_purchase_receipts(connection):
    connection.execute("""CREATE TABLE purchase_receipts(
        id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id),
        received_on TEXT NOT NULL, created_at TEXT NOT NULL, reversed_at TEXT,
        reversal_reason TEXT NOT NULL DEFAULT '')""")
    connection.execute('CREATE UNIQUE INDEX receipt_active ON purchase_receipts(purchase_id) WHERE reversed_at IS NULL')
    connection.execute("""CREATE TABLE receipt_lines(
        id INTEGER PRIMARY KEY, receipt_id INTEGER NOT NULL REFERENCES purchase_receipts(id),
        purchase_line_id INTEGER REFERENCES purchase_lines(id) ON DELETE SET NULL,
        product_id INTEGER NOT NULL REFERENCES products(id), code TEXT NOT NULL, name TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(typeof(quantity)='integer' AND quantity>0),
        UNIQUE(receipt_id,purchase_line_id))""")
    connection.execute('PRAGMA user_version=11')


def migrate_inventory(connection):
    connection.execute("""CREATE TABLE inventory_state(id INTEGER PRIMARY KEY CHECK(id=1),
        initialized INTEGER NOT NULL DEFAULT 0 CHECK(initialized IN(0,1)), mode TEXT,
        initialized_at TEXT, adjustments_enabled INTEGER NOT NULL DEFAULT 0 CHECK(adjustments_enabled IN(0,1)),
        revision INTEGER NOT NULL DEFAULT 0)""")
    connection.execute('INSERT INTO inventory_state(id) VALUES(1)')
    connection.execute('CREATE TABLE inventory_baseline_receipts(receipt_id INTEGER PRIMARY KEY REFERENCES purchase_receipts(id))')
    connection.execute("""CREATE TABLE inventory_movements(id INTEGER PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products(id), delta INTEGER NOT NULL CHECK(typeof(delta)='integer'),
        operation_key TEXT NOT NULL, kind TEXT NOT NULL, reason TEXT NOT NULL, code TEXT NOT NULL,
        name TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(product_id,operation_key))""")
    connection.execute('CREATE INDEX inventory_product ON inventory_movements(product_id,id)')
    connection.execute('PRAGMA user_version=12')


def migrate_purchase_totals(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info(purchase_lines)')}
    if 'total_cost_cents' not in columns:
        connection.execute("ALTER TABLE purchase_lines ADD COLUMN total_cost_cents INTEGER CHECK(total_cost_cents IS NULL OR (typeof(total_cost_cents)='integer' AND total_cost_cents>=0))")
    connection.execute('PRAGMA user_version=15')


def migrate_supplier_alias(connection):
    if 'supplier_alias' not in {r[1] for r in connection.execute('PRAGMA table_info(purchases)')}:
        connection.execute("ALTER TABLE purchases ADD COLUMN supplier_alias TEXT NOT NULL DEFAULT ''")
    connection.execute('PRAGMA user_version=17')


def migrate_purchase_tracking(connection):
    if "tracking_number" not in {r[1] for r in connection.execute("PRAGMA table_info(purchases)")}:
        connection.execute("ALTER TABLE purchases ADD COLUMN tracking_number TEXT NOT NULL DEFAULT ''")
    connection.execute("PRAGMA user_version=18")
