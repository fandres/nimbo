"""Errores y transacciones compartidas."""
import sqlite3
from contextlib import contextmanager

class StorageError(Exception):
    pass

class DuplicateCodeError(StorageError):
    pass

@contextmanager
def operation(connection):
    try:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            yield
    except sqlite3.Error as error:
        raise StorageError('No se pudo guardar o consultar los datos. Revisa permisos, espacio y vuelve a intentarlo.') from error
