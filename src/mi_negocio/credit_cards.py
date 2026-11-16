"""Optional card control: real statement charges, auditable reconciliation."""
import calendar
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from .catalog import ValidationError
from .sales import check_cents
from .storage import operation


def _error(text):
    raise ValidationError({'tarjeta': text})


def _day(value):
    try:
        parsed = value if type(value) is date else date.fromisoformat(value)
    except (ValueError, TypeError):
        _error('Indica una fecha válida.')
    if parsed > date.today(): _error('La fecha no puede estar en el futuro.')
    return parsed.isoformat()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class CreditCardsRepository:
    def __init__(self, connection): self.connection = connection

    def enabled(self):
        return bool(self.connection.execute('SELECT enabled FROM credit_card_settings WHERE id=1').fetchone()[0])

    def _require(self):
        if not self.enabled(): _error('Activa el control de tarjetas en Configuración.')

    def _audit(self, card_id, event_type, details):
        self.connection.execute('INSERT INTO credit_card_events(card_id,event_type,details) VALUES(?,?,?)', (card_id, event_type, _json(details)))

    def set_enabled(self, enabled):
        if type(enabled) is not bool: _error('Indica si el control está activado.')
        with operation(self.connection):
            self.connection.execute('UPDATE credit_card_settings SET enabled=? WHERE id=1', (int(enabled),))
            self._audit(None, 'enabled_changed', {'enabled': enabled})

    def list_cards(self):
        return [dict(r) for r in self.connection.execute('SELECT c.*,a.name,a.enabled FROM credit_cards c JOIN accounts a ON a.id=c.account_id ORDER BY a.name_key')]

    def get(self, card_id):
        row = self.connection.execute('SELECT c.*,a.name,a.enabled FROM credit_cards c JOIN accounts a ON a.id=c.account_id WHERE c.id=?', (card_id,)).fetchone()
        if row is None: _error('La tarjeta ya no existe.')
        return dict(row)

    def save_card(self, name, rate='', rate_unit='monthly', cut_day=None, remind_days=0, card_id=None, expected_revision=None):
        name = name.strip(); rate = str(rate).strip()
        try: number = Decimal(rate or '0')
        except InvalidOperation: _error('Indica una tasa válida.')
        if not name or not number.is_finite() or not 0 <= number <= 1000 or rate_unit not in ('monthly', 'annual', 'effective_annual'):
            _error('Revisa el nombre, la tasa y su unidad.')
        if cut_day is not None and (type(cut_day) is not int or not 1 <= cut_day <= 31): _error('El corte debe estar entre 1 y 31.')
        if type(remind_days) is not int or remind_days not in (0,1,2,3): _error('El aviso debe ser de 0 a 3 días.')
        with operation(self.connection):
            self._require()
            before = self.get(card_id) if card_id is not None else None
            if before:
                if before['revision'] != expected_revision: _error('La tarjeta cambió. Actualiza antes de guardar.')
                self.connection.execute('UPDATE accounts SET name=?,name_key=? WHERE id=?', (name,name.casefold(),before['account_id']))
                self.connection.execute('UPDATE credit_cards SET rate=?,rate_unit=?,cut_day=?,remind_days=?,revision=revision+1 WHERE id=?', (rate,rate_unit,cut_day,remind_days,card_id))
            else:
                account_id = self.connection.execute("INSERT INTO accounts(name,name_key,enabled,kind,is_default) VALUES(?,?,1,'bank',0)", (name,name.casefold())).lastrowid
                card_id = self.connection.execute('INSERT INTO credit_cards(account_id,rate,rate_unit,cut_day,remind_days) VALUES(?,?,?,?,?)', (account_id,rate,rate_unit,cut_day,remind_days)).lastrowid
            result = self.get(card_id)
            self._audit(card_id, 'card_saved', {'before': before, 'after': result})
        return result

    def charge(self, card_id, on, interest_cents, fee_cents, *, request_id, note=''):
        on = _day(on); check_cents(interest_cents); check_cents(fee_cents); check_cents(interest_cents+fee_cents)
        if not isinstance(request_id,str) or not request_id.strip(): _error('Falta el identificador de solicitud.')
        if not interest_cents + fee_cents: _error('Indica un interés o cargo mayor que cero.')
        values = (card_id,on,interest_cents,fee_cents,note.strip())
        with operation(self.connection):
            self._require(); card = self.get(card_id)
            if not card['enabled']: _error('La cuenta de la tarjeta está desactivada.')
            old = self.connection.execute('SELECT * FROM credit_card_charges WHERE request_id=?', (request_id,)).fetchone()
            if old:
                if tuple(old[k] for k in ('card_id','charged_on','interest_cents','fee_cents','note')) != values: _error('La solicitud ya fue utilizada con otros datos.')
                return dict(old)
            key = self.connection.execute('INSERT INTO credit_card_charges(card_id,charged_on,interest_cents,fee_cents,note,request_id) VALUES(?,?,?,?,?,?)', (*values,request_id)).lastrowid
            self._audit(card_id,'charge_added',{'charge_id':key,'interest_cents':interest_cents,'fee_cents':fee_cents})
            return dict(self.connection.execute('SELECT * FROM credit_card_charges WHERE id=?',(key,)).fetchone())

    def cancel_charge(self, id, reason):
        if not reason.strip(): _error('Indica el motivo de anulación.')
        with operation(self.connection):
            self._require()
            row = self.connection.execute('SELECT * FROM credit_card_charges WHERE id=?',(id,)).fetchone()
            if row is None: _error('El cargo ya no existe.')
            if row['cancelled_at']: return
            self.connection.execute('UPDATE credit_card_charges SET cancelled_at=CURRENT_TIMESTAMP,cancellation_reason=? WHERE id=?',(reason.strip(),id))
            self._audit(row['card_id'],'charge_cancelled',{'charge_id':id,'reason':reason.strip()})

    def _money(self):
        from .money_repository import MoneyRepository
        return MoneyRepository(self.connection)

    def debt(self, card_id, as_of=None):
        card = self.get(card_id)
        balance = next(b for b in self._money().balances(as_of=as_of) if b['id']==card['account_id'])
        end = _day(as_of or date.today())
        periods = [p for p in self.periods(card_id) if p['end_on'] >= end and p['start_on'] <= end and not p['provisional']]
        return {'total_cents': -balance['balance_cents'] if balance['configured'] else None, 'configured':balance['configured'], 'provisional':not bool(periods)}

    def reconcile(self, card_id, start, end, confirmed_balance_cents, *, expected_revision=None):
        start = _day(start); end = _day(end)
        if start > end: _error('El inicio debe ser anterior al cierre.')
        if type(confirmed_balance_cents) is not int: _error('Indica el saldo en centavos.')
        check_cents(abs(confirmed_balance_cents))
        with operation(self.connection):
            self._require(); card = self.get(card_id)
            if card['revision'] != expected_revision: _error('La tarjeta cambió. Actualiza antes de conciliar.')
            money = self._money()
            balance = next(b for b in money._balances(end) if b['id']==card['account_id'])
            if not balance['configured']: _error('Configura primero el saldo inicial de la tarjeta.')
            if -balance['balance_cents'] != confirmed_balance_cents: _error('La deuda registrada no coincide con el extracto. Revisa los movimientos.')
            overlaps = self.connection.execute('SELECT id FROM credit_card_periods WHERE card_id=? AND start_on<=? AND end_on>=? AND NOT(start_on=? AND end_on=?)',(card_id,end,start,start,end)).fetchone()
            if overlaps: _error('El período se superpone con otra conciliación.')
            snapshot = _json(money.snapshot(card['account_id'],end))
            self.connection.execute('INSERT INTO credit_card_periods(card_id,start_on,end_on,confirmed_balance_cents,snapshot) VALUES(?,?,?,?,?) ON CONFLICT(card_id,start_on,end_on) DO UPDATE SET confirmed_balance_cents=excluded.confirmed_balance_cents,snapshot=excluded.snapshot,created_at=CURRENT_TIMESTAMP',(card_id,start,end,confirmed_balance_cents,snapshot))
            self.connection.execute('UPDATE credit_cards SET revision=revision+1 WHERE id=?',(card_id,))
            self._audit(card_id,'reconciled',{'start':start,'end':end,'confirmed_balance_cents':confirmed_balance_cents,'snapshot':json.loads(snapshot)})
        return next(p for p in self.periods(card_id) if p['start_on']==start and p['end_on']==end)

    def periods(self, card_id):
        card = self.get(card_id); money = self._money()
        result = []
        for row in self.connection.execute('SELECT * FROM credit_card_periods WHERE card_id=? ORDER BY end_on DESC',(card_id,)):
            item = dict(row)
            item['provisional'] = item['snapshot'] != _json(money.snapshot(card['account_id'],item['end_on']))
            item['status'] = 'pending' if item['provisional'] else 'reconciled'
            result.append(item)
        return result

    def reminders(self, today=None):
        today = today or date.today()
        if isinstance(today,str): today = date.fromisoformat(today)
        if not self.enabled(): return []
        notices = []
        for card in self.list_cards():
            if not card['cut_day'] or not card['enabled']: continue
            cut = today.replace(day=min(card['cut_day'],calendar.monthrange(today.year,today.month)[1]))
            if cut < today:
                month = (today.replace(day=28)+timedelta(days=4)).replace(day=1)
                cut = month.replace(day=min(card['cut_day'],calendar.monthrange(month.year,month.month)[1]))
            if card['remind_days'] and 0 <= (cut-today).days <= card['remind_days']:
                notices.append({'card_id':card['id'],'text':f"{card['name']}: revisa los movimientos antes del corte {cut.isoformat()}. El corte no es la fecha límite de pago."})
            previous = cut
            if cut > today:
                month = cut.replace(day=1)-timedelta(days=1)
                previous = month.replace(day=min(card['cut_day'],month.day))
            periods = self.periods(card['id'])
            opening = self.connection.execute('SELECT opened_on FROM account_openings WHERE account_id=?', (card['account_id'],)).fetchone()
            if opening and opening['opened_on'] <= previous.isoformat() and not any(p['start_on'] <= previous.isoformat() <= p['end_on'] and not p['provisional'] for p in periods):
                notices.append({'card_id':card['id'],'text':f"{card['name']}: pendiente de conciliación al corte {previous.isoformat()}. Saldo provisional; pueden faltar intereses o cargos."})
        return notices

    def events(self, card_id):
        self.get(card_id)
        return [dict(r) for r in self.connection.execute('SELECT * FROM credit_card_events WHERE card_id=? ORDER BY id DESC',(card_id,))]

    def list_charges(self, card_id):
        self.get(card_id)
        return [dict(r) for r in self.connection.execute('SELECT * FROM credit_card_charges WHERE card_id=? ORDER BY charged_on DESC,id DESC',(card_id,))]
