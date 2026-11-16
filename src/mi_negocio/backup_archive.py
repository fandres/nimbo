"""Portable, bounded and verified backups. No live data is changed here."""
from contextlib import closing
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
from tempfile import TemporaryDirectory
import zipfile

from .version import VERSION
from .storage import StorageError

SCHEMA_VERSION = 25
MAX_FILE = 2 * 1024**3
MAX_TOTAL = 8 * 1024**3
MAX_ENTRIES = 100000
MAX_MANIFEST = 16 * 1024**2
PORTABLE_KEYS = (
    'purchases/show_current_month_total', 'sales/require_customer_identification',
    'sales/vat_enabled_default', 'purchases/vat_enabled_default',
    'sales/require_retention_documents',
)


class BackupError(Exception):
    pass


def portable_preferences(values):
    if not isinstance(values, dict) or any(key not in PORTABLE_KEYS or type(value) is not bool for key, value in values.items()):
        raise BackupError('Las preferencias del respaldo no son válidas.')
    return values


def safe_path(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise BackupError('El respaldo contiene una ruta no válida.')
    parts = name.split('/')
    if any(part in ('', '.', '..') or part.endswith((' ', '.')) or any(ord(c)<32 or c in '<>\"|?*' for c in part) for part in parts):
        raise BackupError('El respaldo contiene una ruta no segura.')
    # Reject Windows reserved device paths even when validating on Linux.
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{i}' for p in ('COM', 'LPT') for i in range(1, 10)}
    if any(part.split('.')[0].upper() in reserved for part in parts):
        raise BackupError('El respaldo contiene una ruta no portable.')
    return PurePosixPath(name)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):h.update(chunk)
    return h.hexdigest()


def database_path(connection):
    value = next(r[2] for r in connection.execute('PRAGMA database_list') if r[1] == 'main')
    if not value:raise BackupError('La base debe estar guardada en disco.')
    return Path(value).resolve()


@lru_cache(maxsize=1)
def expected_schema():
    from .database import open_database
    with TemporaryDirectory(prefix='nimbo-schema-') as temp:
        db=open_database(Path(temp)/'schema.sqlite3')
        try:
            return {row[0]:{c[1]:c[2].upper() for c in db.execute('PRAGMA table_info("'+row[0]+'")')}
                    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        finally:db.close()


def check_database(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA trusted_schema=OFF')
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if not 19 <= version <= SCHEMA_VERSION:
            raise BackupError('Versión de base incompatible. Actualiza Nimbo si el respaldo es más reciente.')
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise BackupError('La base del respaldo no supera la comprobación de integridad.')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
            raise BackupError('La base contiene objetos no admitidos por Nimbo.')
        if version==SCHEMA_VERSION:
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table,columns in expected_schema().items():
                actual={c[1]:c[2].upper() for c in db.execute('PRAGMA table_info("'+table+'")')}
                if table not in tables or any(actual.get(name)!=kind for name,kind in columns.items()):
                    raise BackupError('La estructura de la base está incompleta o no es compatible: '+table)
        for table in ('products', 'sales', 'purchases', 'attachments'):
            db.execute('SELECT * FROM '+table+' LIMIT 0')
        attachments = db.execute('SELECT relative_path,removed_at FROM attachments').fetchall()
    return version, attachments


def check_documents(root, attachments):
    for relative, removed in attachments:
        name = safe_path(relative.replace('\\', '/'))
        path = root/'Documentos'/name
        if path.is_symlink() or not path.resolve().is_relative_to((root/'Documentos').resolve()):
            raise BackupError('Un adjunto apunta fuera de Documentos.')
        if not removed and not path.is_file():
            raise BackupError('Falta un documento vigente: '+str(name))


def create_backup(connection, target, preferences):
    target = Path(target).absolute()
    portable_preferences(preferences)
    source = database_path(connection).parent
    if target.resolve().is_relative_to((source/'Documentos').resolve()):
        raise BackupError('Guarda el respaldo fuera de Documentos.')
    if connection.in_transaction:raise BackupError('Termina la operación actual antes de respaldar.')
    published = False
    try:
        if target.exists():raise BackupError('Ya existe ese archivo. Elige otro nombre.')
        target.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix='.nimbo-backup-', dir=target.parent) as temporary:
            stage = Path(temporary)
            with closing(sqlite3.connect(stage/'catalog.sqlite3')) as snapshot:
                connection.backup(snapshot)
            version, attachments = check_database(stage/'catalog.sqlite3')
            # Validate source references; copying the entire folder also keeps historical copies.
            check_documents(source, attachments)
            sources = {'catalog.sqlite3':stage/'catalog.sqlite3'}
            if (source/'logo.png').is_symlink():raise BackupError('El logo no puede ser un enlace.')
            if (source/'logo.png').is_file():sources['logo.png']=source/'logo.png'
            documents = source/'Documentos'
            if documents.is_symlink():raise BackupError('Documentos no puede ser un enlace.')
            if documents.exists():
                for path in documents.rglob('*'):
                    if path.is_symlink():raise BackupError('Documentos contiene enlaces; copia los archivos reales antes de respaldar.')
                    if path.is_file():sources['Documentos/'+path.relative_to(documents).as_posix()]=path
            if len(sources)>MAX_ENTRIES:raise BackupError('Demasiados archivos para un respaldo.')
            manifest = dict(format='nimbo-backup',format_version=1,app_version=VERSION,
                            schema_version=version,created_at=datetime.now(timezone.utc).isoformat(),
                            preferences=preferences,files={})
            total = 0; names = set()
            archive = stage/'archive.zip'
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as output:
                for name,path in sources.items():
                    safe_path(name)
                    if name.casefold() in names:raise BackupError('Hay nombres de archivos incompatibles entre Linux y Windows.')
                    names.add(name.casefold()); size=path.stat().st_size; total+=size
                    if size>MAX_FILE or total>MAX_TOTAL:raise BackupError('El respaldo supera el límite de tamaño permitido.')
                    manifest['files'][name]={'size':size,'sha256':digest(path)}
                    output.write(path,name)
                encoded=json.dumps(manifest,ensure_ascii=False).encode('utf-8')
                if len(encoded)>MAX_MANIFEST:raise BackupError('El manifiesto supera el tamaño permitido.')
                output.writestr('manifest.json',encoded)
            # Re-read bytes and SQLite, not just trust the ZIP writer.
            unpack_backup(archive,stage/'verified')
            with archive.open('r+b') as stream:os.fsync(stream.fileno())
            # Reserve exclusively, then atomically replace only our own placeholder.
            with target.open('xb'):pass
            published=True
            os.replace(archive,target)
            return manifest
    except (OSError,StorageError,sqlite3.Error,zipfile.BadZipFile,ValueError) as error:
        if published:target.unlink(missing_ok=True)
        raise BackupError('No se pudo crear el respaldo: '+str(error)) from error


def unpack_backup(archive, destination):
    destination=Path(destination).absolute()
    created=False
    try:
        destination.mkdir(parents=True,exist_ok=False);created=True
        with zipfile.ZipFile(archive) as source:
            entries=source.infolist()
            if len(entries)>MAX_ENTRIES+1:raise BackupError('Demasiados archivos en el respaldo.')
            names=set();total=0
            for entry in entries:
                safe_path(entry.filename)
                if entry.is_dir() or entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16):
                    raise BackupError('El respaldo contiene entradas no admitidas.')
                folded=entry.filename.casefold()
                if folded in names:raise BackupError('El respaldo contiene rutas duplicadas.')
                names.add(folded);total+=entry.file_size
                if entry.file_size>MAX_FILE or total>MAX_TOTAL:raise BackupError('El respaldo supera el límite de tamaño permitido.')
            info=source.getinfo('manifest.json')
            if info.file_size>MAX_MANIFEST:raise BackupError('Manifiesto demasiado grande.')
            manifest=json.loads(source.read(info))
            if not isinstance(manifest,dict) or manifest.get('format')!='nimbo-backup' or manifest.get('format_version')!=1:
                raise BackupError('Este archivo no es un respaldo completo de Nimbo compatible.')
            portable_preferences(manifest.get('preferences'))
            files=manifest.get('files')
            if not isinstance(files,dict) or 'catalog.sqlite3' not in files:raise BackupError('Falta la base del respaldo.')
            if set(files)|{'manifest.json'} != {e.filename for e in entries}:raise BackupError('El inventario del respaldo no coincide con sus archivos.')
            for name, expected in files.items():
                if name not in ('catalog.sqlite3','logo.png') and not name.startswith('Documentos/'):
                    raise BackupError('Archivo no permitido en el respaldo: '+name)
                if not isinstance(expected,dict) or type(expected.get('size')) is not int or not isinstance(expected.get('sha256'),str):
                    raise BackupError('Inventario de archivos no válido.')
                entry=source.getinfo(name)
                if entry.file_size!=expected['size']:raise BackupError('Tamaño incorrecto: '+name)
                path=destination/safe_path(name);path.parent.mkdir(parents=True,exist_ok=True)
                with source.open(entry) as incoming,path.open('xb') as outgoing:
                    shutil.copyfileobj(incoming,outgoing,1024*1024)
                if digest(path)!=expected['sha256']:raise BackupError('El archivo está dañado: '+name)
        version,attachments=check_database(destination/'catalog.sqlite3')
        if version!=manifest.get('schema_version'):raise BackupError('La versión de la base no coincide con el manifiesto.')
        check_documents(destination,attachments)
        return manifest
    except (BackupError,OSError,StorageError,sqlite3.Error,zipfile.BadZipFile,ValueError,KeyError,TypeError,RuntimeError) as error:
        if created:shutil.rmtree(destination,ignore_errors=True)
        if isinstance(error,BackupError):raise
        raise BackupError('No se pudo validar el respaldo: '+str(error)) from error
