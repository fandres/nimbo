"""Migración 13: gastos y préstamos sin modificar ventas ni inventario."""

def migrate_expenses(connection):
    statements=[
        '''CREATE TABLE expense_categories(id INTEGER PRIMARY KEY,name TEXT NOT NULL CHECK(length(trim(name))>0),
            name_key TEXT NOT NULL UNIQUE,enabled INTEGER NOT NULL CHECK(enabled IN(0,1)))''',
        '''CREATE TABLE expenses(id INTEGER PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,request_payload TEXT NOT NULL,
            concept TEXT NOT NULL CHECK(length(trim(concept))>0),amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents>0),
            spent_on TEXT NOT NULL,category_id INTEGER NOT NULL REFERENCES expense_categories(id),
            paid_on TEXT,account_id INTEGER REFERENCES accounts(id),due_on TEXT,note TEXT NOT NULL,voucher TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,cancelled_at TEXT,
            cancellation_reason TEXT NOT NULL DEFAULT '',CHECK((paid_on IS NULL AND account_id IS NULL) OR (paid_on IS NOT NULL AND account_id IS NOT NULL)))''',
        '''CREATE TABLE expense_revisions(id INTEGER PRIMARY KEY,expense_id INTEGER NOT NULL REFERENCES expenses(id),
            revision INTEGER NOT NULL,changed_at TEXT NOT NULL,snapshot TEXT NOT NULL,UNIQUE(expense_id,revision))''',
        '''CREATE TABLE loans(id INTEGER PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,request_payload TEXT NOT NULL,
            name TEXT NOT NULL CHECK(length(trim(name))>0),opened_on TEXT NOT NULL,
            principal_cents INTEGER NOT NULL CHECK(typeof(principal_cents)='integer' AND principal_cents>0),
            revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL)''',
        '''CREATE TABLE loan_payments(id INTEGER PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,request_payload TEXT NOT NULL,
            loan_id INTEGER NOT NULL REFERENCES loans(id),paid_on TEXT NOT NULL,account_id INTEGER NOT NULL REFERENCES accounts(id),
            capital_cents INTEGER NOT NULL CHECK(typeof(capital_cents)='integer' AND capital_cents>=0),
            interest_cents INTEGER NOT NULL CHECK(typeof(interest_cents)='integer' AND interest_cents>=0),
            note TEXT NOT NULL,created_at TEXT NOT NULL,cancelled_at TEXT,cancellation_reason TEXT NOT NULL DEFAULT '',
            CHECK(capital_cents>0 OR interest_cents>0))''',
        '''CREATE TABLE loan_events(id INTEGER PRIMARY KEY,loan_id INTEGER NOT NULL REFERENCES loans(id),
            changed_at TEXT NOT NULL,description TEXT NOT NULL,snapshot TEXT NOT NULL)''',
        'CREATE INDEX expenses_date ON expenses(spent_on)',
        'CREATE INDEX loan_payments_parent ON loan_payments(loan_id)',
    ]
    for statement in statements:connection.execute(statement)
    for name in ('Insumos y taller','Marketing','Software','Servicios','Salud y pensión','Intereses','Otros'):
        connection.execute('INSERT INTO expense_categories(name,name_key,enabled) VALUES(?,?,1)',(name,name.casefold()))
    connection.execute('PRAGMA user_version=13')
