"""Cuenta auxiliar de retenciones; sus saldos no son efectivo disponible."""
from .sales import informative_withholding

ACCOUNT_ID = -1
ACCOUNT_NAME = 'Retenciones de renta'

def deducted(row):
    return informative_withholding(row['total_cents']) if row['has_withholding'] and row['withholding_deducted'] else 0

def migrate_withholding(connection):
    columns={r[1] for r in connection.execute('PRAGMA table_info(sales)')}
    if 'withholding_deducted' not in columns:
        connection.execute('ALTER TABLE sales ADD COLUMN withholding_deducted INTEGER NOT NULL DEFAULT 0')
    connection.execute('PRAGMA user_version=22')
