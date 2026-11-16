"""Recoverable restore, called with the instance lock held and SQLite closed."""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4
from .backup_archive import (BackupError,create_backup,unpack_backup,database_path,
                             check_database,check_documents,portable_preferences)
from .database import open_database

STAGE = '.nimbo-restore'


def sync_directory(path):
    if os.name != 'nt':
        fd=os.open(path,os.O_RDONLY | os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)


def write_journal(stage,journal):
    temp=stage/'journal.tmp'
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(journal,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,stage/'journal.json');sync_directory(stage)


def components(db):
    return (db.name,'Documentos','logo.png',db.name+'-wal',db.name+'-shm')


def remove(path):
    if path.is_dir() and not path.is_symlink():shutil.rmtree(path)
    else:path.unlink(missing_ok=True)


def prepare_restore(connection,archive,preferences):
    db=database_path(connection);stage=db.parent/STAGE
    if stage.exists():raise BackupError('Hay una recuperación pendiente. Cierra y vuelve a abrir Nimbo.')
    stage.mkdir()
    try:
        incoming=stage/'incoming'
        manifest=unpack_backup(archive,incoming)
        # Migration and path normalization affect only the validated staged copy.
        migrated=open_database(incoming/'catalog.sqlite3')
        try:
            with migrated:
                migrated.execute("UPDATE attachments SET relative_path=replace(relative_path,char(92),'/')")
        finally:migrated.close()
        _,attachments=check_database(incoming/'catalog.sqlite3');check_documents(incoming,attachments)
        if db.name!='catalog.sqlite3':os.replace(incoming/'catalog.sqlite3',incoming/db.name)
        (incoming/'Documentos').mkdir(exist_ok=True)
        for file in incoming.rglob('*'):
            if file.is_file():
                with file.open('r+b') as stream:os.fsync(stream.fileno())
        for folder in sorted((p for p in incoming.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):sync_directory(folder)
        sync_directory(incoming);sync_directory(stage);sync_directory(db.parent)
        safety=db.parent/'Respaldos'/('Nimbo-antes-de-restaurar-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:8]+'.zip')
        create_backup(connection,safety,preferences)
        journal=dict(state='prepared',database=db.name,old_preferences=preferences,
                     new_preferences=manifest['preferences'],safety=str(safety))
        write_journal(stage,journal)
        return safety
    except Exception as error:
        shutil.rmtree(stage,ignore_errors=True)
        if isinstance(error,BackupError):raise
        raise BackupError('No se pudo preparar la restauración: '+str(error)) from error


def read_journal(db):
    stage=db.parent/STAGE
    if stage.is_symlink():raise BackupError('La carpeta de recuperación no es válida.')
    try:
        journal=json.loads((stage/'journal.json').read_text(encoding='utf-8'))
        if journal['database']!=db.name or journal['state'] not in ('prepared','applying','committed'):
            raise ValueError('Estado no válido')
        portable_preferences(journal['old_preferences']);portable_preferences(journal['new_preferences'])
        if journal['state']!='prepared':
            if set(journal['had'])!=set(components(db)) or any(type(v) is not bool for v in journal['had'].values()):
                raise ValueError('Inventario no válido')
        return journal
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise BackupError('No se pudo leer el registro de recuperación. Se conservaron los archivos para revisión.') from error


def recover_restore(db,apply_preferences):
    """Rollback an incomplete swap or finish cleanup after its commit point."""
    db=Path(db).resolve();stage=db.parent/STAGE
    if not stage.exists():return None
    if stage.is_symlink():raise BackupError('La carpeta de recuperación no es válida.')
    if not (stage/'journal.json').exists():
        # No swap can start until a durable journal exists.
        shutil.rmtree(stage);return 'Se descartó una preparación de respaldo incompleta.'
    journal=read_journal(db)
    if journal['state']=='applying':
        for name in components(db):
            current=db.parent/name;old=stage/'original'/name
            if old.exists():
                remove(current);os.replace(old,current);sync_directory(db.parent)
            elif not journal['had'][name]:remove(current)
        apply_preferences(journal['old_preferences'])
    state=journal['state']
    shutil.rmtree(stage);sync_directory(db.parent)
    return ('Restauración completada; se finalizó su limpieza.' if state=='committed'
            else 'Se recuperó el estado anterior; la restauración no había terminado.')


def apply_restore(db,apply_preferences):
    db=Path(db).resolve();stage=db.parent/STAGE
    journal=read_journal(db)
    if journal['state']!='prepared':raise BackupError('La restauración no está preparada.')
    try:
        original=stage/'original';original.mkdir()
        journal['had']={name:(db.parent/name).exists() for name in components(db)}
        journal['state']='applying';write_journal(stage,journal)
        for name in components(db):
            current=db.parent/name
            if current.is_symlink():raise BackupError('No se pueden sustituir datos enlazados a otra ubicación.')
            if journal['had'][name]:os.replace(current,original/name)
            incoming=stage/'incoming'/name
            if incoming.exists():os.replace(incoming,current)
            sync_directory(db.parent);sync_directory(original);sync_directory(stage/'incoming')
        apply_preferences(journal['new_preferences'])
        journal['state']='committed';write_journal(stage,journal)
    except Exception as error:
        try:recover_restore(db,apply_preferences)
        except Exception as recovery:
            raise BackupError('La restauración se interrumpió. La recuperación sigue pendiente; vuelve a abrir Nimbo. '+str(recovery)) from error
        raise BackupError('No se restauró el respaldo. Se recuperaron los datos anteriores: '+str(error)) from error
    recover_restore(db,apply_preferences)
