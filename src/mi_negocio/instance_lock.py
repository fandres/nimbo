"""Bloqueo cooperativo de una instancia por base local, antes de abrir SQLite."""
from pathlib import Path
from PySide6.QtCore import QLockFile


class InstanceLockError(Exception):
    """No fue posible asegurar el acceso exclusivo; no se debe abrir la base."""


class InstanceAlreadyRunning(InstanceLockError):
    """Otra instancia mantiene el bloqueo de esta base."""


class DatabaseInstanceLock:
    def __init__(self, database_path: Path):
        try:
            self.database_path=Path(database_path).expanduser().resolve()
        except (OSError, RuntimeError) as error:
            raise InstanceLockError('No se pudo resolver la ubicación de la base de datos.') from error
        self.lock_path=self.database_path.with_name(self.database_path.name+'.lock')
        self._lock=QLockFile(str(self.lock_path))
        # This lock lives for the whole session. Age never proves that it is stale.
        # Qt can still recover locks whose owning process has actually terminated.
        self._lock.setStaleLockTime(0)

    def acquire(self):
        if self._lock.isLocked():return self
        try:
            self.database_path.parent.mkdir(parents=True,exist_ok=True)
        except OSError as error:
            raise InstanceLockError('No se pudo preparar la carpeta de datos. Revisa la ubicación y los permisos.') from error
        if self._lock.tryLock(0):return self
        if self._lock.error()==QLockFile.LockFailedError:
            raise InstanceAlreadyRunning('Nimbo ya está abierto con esta base de datos. Usa la ventana existente o ciérrala antes de volver a abrir el programa.')
        if self._lock.error()==QLockFile.PermissionError:
            raise InstanceLockError('No se pudo proteger la base de datos. Revisa los permisos de su carpeta.')
        raise InstanceLockError('No se pudo proteger la base de datos. Revisa permisos y espacio disponible antes de intentar nuevamente.')

    def release(self):
        # Never delete files ourselves or release a lock owned by another process.
        if self._lock.isLocked():self._lock.unlock()

    def __enter__(self):return self.acquire()

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
