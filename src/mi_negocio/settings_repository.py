"""Cuentas y formas de pago editables; nunca se borran históricos."""
from decimal import Decimal
from .commissions import encode_tiers, decode_tiers
from .sales import Account, PaymentMethod, check_cents
from .catalog import ValidationError
from .storage import operation, StorageError


class SettingsRepository:
    def __init__(self, connection): self.connection = connection

    def list_methods(self, include_disabled=False):
        with operation(self.connection):
            rows=self.connection.execute('SELECT * FROM payment_methods'+('' if include_disabled else ' WHERE enabled=1')+' ORDER BY id').fetchall()
        return [PaymentMethod(r['id'],r['name'],r['provider'],Decimal(r['rate_percent']),r['fixed_cents'],bool(r['enabled']),r['placement'],bool(r['default_received']),r['account_kind'],decode_tiers(r['tiers_json'])) for r in rows]

    def list_accounts(self, include_disabled=False, include_cards=False):
        with operation(self.connection):
            clauses=[]
            if not include_disabled:clauses.append('enabled=1')
            if not include_cards:clauses.append('id NOT IN (SELECT account_id FROM credit_cards)')
            elif not self.connection.execute('SELECT enabled FROM credit_card_settings WHERE id=1').fetchone()[0]:
                if not include_disabled:clauses.append('id NOT IN (SELECT account_id FROM credit_cards)')
            rows=self.connection.execute('SELECT * FROM accounts'+(' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY id').fetchall()
        return [Account(r['id'],r['name'],bool(r['enabled']),r['kind'],bool(r['is_default'])) for r in rows]

    def save_account(self, account):
        name=account.name.strip()
        if account.kind not in ('cash','bank'): raise ValidationError({'tipo':'Selecciona el tipo de cuenta.'})
        if not name: raise ValidationError({'nombre':'Escribe un nombre.'})
        with operation(self.connection):
            if account.is_default:
                self.connection.execute('UPDATE accounts SET is_default=0 WHERE kind=?',(account.kind,))
            if account.id:
                cursor=self.connection.execute('UPDATE accounts SET name=?,name_key=?,enabled=?,kind=?,is_default=? WHERE id=?',(name,name.casefold(),int(account.enabled),account.kind,int(account.is_default),account.id))
                if cursor.rowcount!=1: raise StorageError('La cuenta ya no existe.')
                key=account.id
            else:
                key=self.connection.execute('INSERT INTO accounts(name,name_key,enabled,kind,is_default) VALUES(?,?,?,?,?)',(name,name.casefold(),int(account.enabled),account.kind,int(account.is_default))).lastrowid
        return Account(key,name,account.enabled,account.kind,account.is_default)

    def save_method(self, method):
        tiers_json=encode_tiers(method.tiers)
        name=method.name.strip(); rate=method.rate_percent
        check_cents(method.fixed_cents)
        if not name or not rate.is_finite() or not 0<=rate<=100 or rate.as_tuple().exponent < -6 or method.placement not in ('primary','additional') or method.account_kind not in ('any','cash','bank'):
            raise ValidationError({'forma':'Revisa nombre, porcentaje (0–100, hasta 6 decimales) y ubicación.'})
        values=(name,name.casefold(),method.provider.strip(),str(rate),method.fixed_cents,int(method.enabled),method.placement,int(method.default_received),method.account_kind,tiers_json)
        with operation(self.connection):
            if method.id:
                cursor=self.connection.execute('UPDATE payment_methods SET name=?,name_key=?,provider=?,rate_percent=?,fixed_cents=?,enabled=?,placement=?,default_received=?,account_kind=?,tiers_json=? WHERE id=?',(*values,method.id))
                if cursor.rowcount!=1: raise StorageError('La forma de pago ya no existe.')
                key=method.id
            else:
                key=self.connection.execute('INSERT INTO payment_methods(name,name_key,provider,rate_percent,fixed_cents,enabled,placement,default_received,account_kind,tiers_json) VALUES(?,?,?,?,?,?,?,?,?,?)',values).lastrowid
        return PaymentMethod(key,name,method.provider.strip(),rate,method.fixed_cents,method.enabled,method.placement,method.default_received,method.account_kind,method.tiers)

    def list_carriers(self, include_disabled=False):
        with operation(self.connection):
            return [dict(r) for r in self.connection.execute('SELECT * FROM carriers'+('' if include_disabled else ' WHERE enabled=1')+' ORDER BY name_key')]

    def save_carrier(self, carrier_id, name, enabled=True):
        name = name.strip()
        if not name:
            raise ValidationError({'transportadora': 'Escribe el nombre de la transportadora.'})
        with operation(self.connection):
            if carrier_id:
                if self.connection.execute('UPDATE carriers SET name=?,name_key=?,enabled=? WHERE id=?', (name,name.casefold(),int(enabled),carrier_id)).rowcount != 1:
                    raise StorageError('La transportadora ya no existe.')
                return carrier_id
            return self.connection.execute('INSERT INTO carriers(name,name_key,enabled) VALUES(?,?,?)',(name,name.casefold(),int(enabled))).lastrowid
