"""Treasury records; existing commercial sources remain authoritative."""
def migrate_money(c):
    c.execute('''CREATE TABLE account_openings(account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
        opened_on TEXT NOT NULL,amount_cents INTEGER NOT NULL,revision INTEGER NOT NULL DEFAULT 1)''')
    c.execute('''CREATE TABLE money_entries(id INTEGER PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,request_payload TEXT NOT NULL,
        kind TEXT NOT NULL,occurred_on TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents>0),
        concept TEXT NOT NULL,from_account INTEGER REFERENCES accounts(id),to_account INTEGER REFERENCES accounts(id),
        purchase_id INTEGER REFERENCES purchases(id),purchase_category TEXT NOT NULL DEFAULT '',capital_cents INTEGER NOT NULL DEFAULT 0,interest_cents INTEGER NOT NULL DEFAULT 0,fee_cents INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,
        cancelled_at TEXT,cancellation_reason TEXT NOT NULL DEFAULT '')''')
    c.execute('''CREATE TABLE money_events(id INTEGER PRIMARY KEY,entity TEXT NOT NULL,entity_id INTEGER NOT NULL,
        changed_at TEXT NOT NULL,description TEXT NOT NULL,snapshot TEXT NOT NULL)''')
    from .credit_card_schema import migrate_credit_cards
    migrate_credit_cards(c)
    c.execute('PRAGMA user_version=14')
