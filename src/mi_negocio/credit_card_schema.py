"""Credit card tables; migration transaction is owned by the caller."""
def migrate_credit_cards(connection):
    statements = [
        '''CREATE TABLE credit_card_settings(id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)))''',
        'INSERT INTO credit_card_settings(id,enabled) VALUES(1,0)',
        '''CREATE TABLE credit_cards(id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL UNIQUE REFERENCES accounts(id), rate TEXT NOT NULL DEFAULT '', rate_unit TEXT NOT NULL DEFAULT 'monthly', cut_day INTEGER CHECK(cut_day BETWEEN 1 AND 31), remind_days INTEGER NOT NULL DEFAULT 0 CHECK(remind_days BETWEEN 0 AND 3), revision INTEGER NOT NULL DEFAULT 1)''',
        '''CREATE TABLE credit_card_charges(id INTEGER PRIMARY KEY, card_id INTEGER NOT NULL REFERENCES credit_cards(id), charged_on TEXT NOT NULL, interest_cents INTEGER NOT NULL CHECK(interest_cents>=0), fee_cents INTEGER NOT NULL CHECK(fee_cents>=0), note TEXT NOT NULL DEFAULT '', request_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, cancelled_at TEXT, cancellation_reason TEXT)''',
        '''CREATE TABLE credit_card_periods(id INTEGER PRIMARY KEY,card_id INTEGER NOT NULL REFERENCES credit_cards(id),start_on TEXT NOT NULL,end_on TEXT NOT NULL,confirmed_balance_cents INTEGER NOT NULL,snapshot TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(card_id,start_on,end_on))''',
        '''CREATE TABLE credit_card_events(id INTEGER PRIMARY KEY,card_id INTEGER REFERENCES credit_cards(id),event_type TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
    ]
    for statement in statements: connection.execute(statement)
