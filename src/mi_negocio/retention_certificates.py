"""Annual certificate workflow, independent of sale amounts and bank movements."""
from datetime import date,datetime,timezone
from .sales import SalesFilter
from .sales_repository import SalesRepository
from .storage import StorageError,operation

STATUSES={'pending':'Pendiente de solicitar','requested':'Solicitado','received':'Recibido'}


def customer_key(sale):
    document=' '.join(sale['customer_identification'].split()).upper()
    return 'id:'+document if document else 'name:'+' '.join(sale['customer_name'].split()).casefold()


def migrate_certificates(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS retention_certificates(
        year INTEGER NOT NULL,customer_key TEXT NOT NULL,status TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL,updated_at TEXT NOT NULL,
        PRIMARY KEY(year,customer_key),CHECK(status IN ('pending','requested','received')))''')
    connection.execute('''CREATE TABLE IF NOT EXISTS retention_certificate_events(
        id INTEGER PRIMARY KEY,year INTEGER NOT NULL,customer_key TEXT NOT NULL,
        status TEXT NOT NULL,note TEXT NOT NULL,changed_at TEXT NOT NULL)''')
    connection.execute('PRAGMA user_version=27')


def migrate_certificate_documents(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS retention_certificate_documents(
        id INTEGER PRIMARY KEY,year INTEGER NOT NULL,customer_key TEXT NOT NULL,
        UNIQUE(year,customer_key))''')
    connection.execute('PRAGMA user_version=28')


class RetentionCertificatesRepository:
    def __init__(self,connection):
        self.connection=connection
        self.sales=SalesRepository(connection)

    def list(self,start,end,query='',status=None):
        if type(start) is not date or type(end) is not date or start>end:
            raise StorageError('Revisa el período del informe de retenciones.')
        if status is not None and status not in STATUSES:
            raise StorageError('Selecciona un estado de certificado válido.')
        rows=self.sales.list_sales(SalesFilter(start=start,end=end,has_withholding=True,cancelled=False))
        with operation(self.connection):
            saved={(r['year'],r['customer_key']):dict(r) for r in self.connection.execute('SELECT * FROM retention_certificates WHERE year BETWEEN ? AND ?',(start.year,end.year))}
        groups={}
        for sale in rows:
            year=date.fromisoformat(sale['sold_on']).year;key=customer_key(sale)
            group=groups.setdefault((year,key),dict(year=year,customer_key=key,
                name=sale['customer_name'],identification=sale['customer_identification'],
                missing_identification=not sale['customer_identification'].strip(),
                sales=[],withholding_cents=0,booked_cents=0,informative_cents=0,
                status='pending',note='',revision=0,updated_at=''))
            group['sales'].append(sale)
            amount=sale['withholding_cents'];group['withholding_cents']+=amount
            if not sale['withholding_deducted']:group['informative_cents']+=amount
            elif sale['received']:group['booked_cents']+=amount
        needle=query.strip().casefold()
        result=[]
        for identity,group in groups.items():
            group.update(saved.get(identity,{}))
            if status is not None and group['status']!=status:continue
            # Search selects complete client/year groups, never silently drops their invoices.
            if needle and not any(needle in str(s.get(field,'')).casefold() for s in group['sales']
                for field in ('customer_name','customer_identification','customer_email','customer_alias','invoice_ref')):continue
            result.append(group)
        return sorted(result,key=lambda g:(-g['year'],g['name'].casefold(),g['customer_key']))

    def save(self,year,key,status,note,*,expected_revision):
        if type(year) is not int or not 1<=year<=9999 or status not in STATUSES:
            raise StorageError('Revisa el año y el estado del certificado.')
        if not isinstance(note,str) or len(note.strip())>2000:
            raise StorageError('La nota debe tener hasta 2000 caracteres.')
        if not any(g['customer_key']==key for g in self.list(date(year,1,1),date(year,12,31))):
            raise StorageError('No hay ventas vigentes con retención para este cliente y año. Actualiza el informe.')
        with operation(self.connection):
            previous=self.connection.execute('SELECT * FROM retention_certificates WHERE year=? AND customer_key=?',(year,key)).fetchone()
            revision=previous['revision'] if previous else 0
            if revision!=expected_revision:raise StorageError('El seguimiento cambió. Actualiza antes de guardar.')
            if previous and previous['status']==status and previous['note']==note.strip():return revision
            changed=datetime.now(timezone.utc).isoformat()
            self.connection.execute('''INSERT INTO retention_certificates VALUES(?,?,?,?,?,?)
                ON CONFLICT(year,customer_key) DO UPDATE SET status=excluded.status,note=excluded.note,
                revision=excluded.revision,updated_at=excluded.updated_at''',(year,key,status,note.strip(),revision+1,changed))
            self.connection.execute('INSERT INTO retention_certificate_events(year,customer_key,status,note,changed_at) VALUES(?,?,?,?,?)',
                (year,key,status,note.strip(),changed))
            return revision+1

    def document_owner(self,year,key,*,create=True):
        if type(year) is not int or not 1<=year<=9999 or not isinstance(key,str):
            raise StorageError('Revisa el cliente y año del certificado.')
        if create and not any(g['customer_key']==key for g in self.list(date(year,1,1),date(year,12,31))):
            raise StorageError('Actualiza el informe: no hay ventas vigentes con retención para este cliente y año.')
        with operation(self.connection):
            if create:
                self.connection.execute('INSERT OR IGNORE INTO retention_certificate_documents(year,customer_key) VALUES(?,?)',(year,key))
            row=self.connection.execute('SELECT id FROM retention_certificate_documents WHERE year=? AND customer_key=?',(year,key)).fetchone()
            return row['id'] if row else None

    def history(self,year,key):
        with operation(self.connection):
            return [dict(r) for r in self.connection.execute('SELECT * FROM retention_certificate_events WHERE year=? AND customer_key=? ORDER BY id DESC',(year,key))]
