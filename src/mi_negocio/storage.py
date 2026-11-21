"""Errores y transacciones compartidas."""
import sqlite3
from contextlib import contextmanager
from uuid import uuid4

class StorageError(Exception):
    pass

class DuplicateCodeError(StorageError):
    pass

@contextmanager
def operation(connection):
    try:
        if connection.in_transaction:
            name='nested_'+uuid4().hex
            connection.execute('SAVEPOINT '+name)
            try:
                yield
            except BaseException:
                connection.execute('ROLLBACK TO '+name)
                connection.execute('RELEASE '+name)
                raise
            else:
                connection.execute('RELEASE '+name)
        else:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                yield
    except sqlite3.Error as error:
        raise StorageError('No se pudo guardar o consultar los datos. Revisa permisos, espacio y vuelve a intentarlo.') from error
