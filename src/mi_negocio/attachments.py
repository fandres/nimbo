"""Copias locales de comprobantes; SQLite conserva rutas relativas portables."""
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
import shutil
import sqlite3
from .storage import StorageError

OWNERS = {
    'expense': ('expenses','spent_on','Gastos'),
    'purchase': ('purchases','purchased_on','Compras'),
    'sale': ('sales','sold_on','Ventas'),
    'loan_payment': ('loan_payments','paid_on','Gastos'),
    'card_charge': ('credit_card_charges','charged_on','Gastos'),
}
EXTENSIONS = {'.pdf','.png','.jpg','.jpeg'}


def migrate_attachments(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY, owner_kind TEXT NOT NULL, owner_id INTEGER NOT NULL,
        original_name TEXT NOT NULL, relative_path TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL, removed_at TEXT)''')
    connection.execute('CREATE INDEX IF NOT EXISTS attachments_owner ON attachments(owner_kind,owner_id)')
    connection.execute('PRAGMA user_version=19')


class AttachmentsRepository:
    def __init__(self,connection):
        self.connection=connection
        filename=next(r[2] for r in connection.execute('PRAGMA database_list') if r[1]=='main')
        if not filename:raise StorageError('Los adjuntos necesitan una base de datos guardada en disco.')
        self.root=Path(filename).resolve().parent/'Documentos'

    def list(self,kind,key):
        try:
            return [dict(r) for r in self.connection.execute('SELECT * FROM attachments WHERE owner_kind=? AND owner_id=? AND removed_at IS NULL ORDER BY id',(kind,key))]
        except sqlite3.Error as error:raise StorageError('No se pudieron consultar los adjuntos.') from error

    def path(self,row):
        target=(self.root/row['relative_path']).resolve()
        if not target.is_relative_to(self.root.resolve()):raise StorageError('La ruta del adjunto no es válida.')
        return target

    def add(self,kind,key,source):
        source=Path(source)
        if kind not in OWNERS:raise StorageError('Tipo de registro no válido.')
        if source.suffix.lower() not in EXTENSIONS:raise StorageError('Selecciona un PDF, PNG o JPG.')
        table,column,folder=OWNERS[kind]
        target=None
        try:
            row=self.connection.execute(f'SELECT {column} FROM {table} WHERE id=?',(key,)).fetchone()
            if row is None:raise StorageError('Guarda primero el registro para adjuntar documentos.')
            day=date.fromisoformat(row[0])
            relative=Path(str(day.year))/f'{day.month:02}'/folder/f'{kind}-{key}'/(uuid4().hex+source.suffix.lower())
            target=self.path({'relative_path':str(relative)})
            target.parent.mkdir(parents=True,exist_ok=True)
            # Exclusive creation prevents replacing another copy, including on retry.
            with source.open('rb') as incoming, target.open('xb') as outgoing:
                shutil.copyfileobj(incoming,outgoing)
            with self.connection:
                cursor=self.connection.execute('INSERT INTO attachments(owner_kind,owner_id,original_name,relative_path,created_at) VALUES(?,?,?,?,?)',
                    (kind,key,source.name,relative.as_posix(),datetime.now(timezone.utc).isoformat()))
                saved=dict(self.connection.execute('SELECT * FROM attachments WHERE id=?',(cursor.lastrowid,)).fetchone())
            return saved
        except (OSError,sqlite3.Error,ValueError) as error:
            if target is not None:
                try:target.unlink(missing_ok=True)
                except OSError:pass
            raise StorageError('No se pudo copiar el documento. Revisa el archivo, los permisos y el espacio disponible.') from error

    def remove(self,key):
        try:
            with self.connection:self.connection.execute('UPDATE attachments SET removed_at=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),key))
        except sqlite3.Error as error:raise StorageError('No se pudo quitar el adjunto.') from error
