"""Punto de entrada y ubicación persistente de los datos."""

from pathlib import Path
import sys

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from .repository import CatalogRepository, StorageError
from .instance_lock import DatabaseInstanceLock, InstanceAlreadyRunning, InstanceLockError
from .ui.main_window import MainWindow
from .backup_archive import BackupError
from .backup_restore import recover_restore, apply_restore
from .backup_preferences import BackupPreferences
from .branding import app_icon
from .version import APP_NAME, VERSION, DISPLAY_VERSION


def configure_identity(application: QApplication) -> None:
    application.setOrganizationName('Fandres')
    # Keep the storage identity so existing databases remain in the same folder.
    application.setApplicationName('MiNegocio')
    application.setApplicationDisplayName(APP_NAME)
    application.setApplicationVersion(VERSION)
    application.setWindowIcon(app_icon())


def data_directory() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))


def smoke_test() -> int:
    """Comprueba Qt, SQLite y arranque usando solo datos temporales."""
    from tempfile import TemporaryDirectory
    from PySide6.QtCore import QTimer
    application = QApplication.instance() or QApplication(sys.argv)
    configure_identity(application)
    assert not application.windowIcon().pixmap(32,32).isNull(), "Missing bundled Nimbo icon"
    with TemporaryDirectory(prefix='nimbo-smoke-') as temporary:
        with DatabaseInstanceLock(Path(temporary) / 'smoke.sqlite3') as guard:
            repository = CatalogRepository(guard.database_path)
            try:
                window = MainWindow(repository)
                window.show()
                QTimer.singleShot(100, application.quit)
                result = application.exec()
                assert repository.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                window.close()
                return result
            finally:
                repository.close()


def main() -> int:
    if '--version' in sys.argv:
        print(f'{APP_NAME} {DISPLAY_VERSION}')
        return 0
    if '--smoke-test' in sys.argv:
        return smoke_test()
    application = QApplication.instance() or QApplication(sys.argv)
    configure_identity(application)
    directory = data_directory()
    try:
        with DatabaseInstanceLock(directory / 'catalog.sqlite3') as guard:
            preferences=BackupPreferences()
            recovery=recover_restore(guard.database_path,preferences.apply)
            repository = CatalogRepository(guard.database_path)
            pending_restore=False
            try:
                window = MainWindow(repository, directory / 'logo.png')
                def request_restore():
                    nonlocal pending_restore
                    pending_restore=True
                    window.close()
                    application.quit()
                window.settings_page.backup_page.restore_requested.connect(request_restore)
                window.show()
                from PySide6.QtCore import QTimer
                def startup():
                    if recovery:QMessageBox.information(window,'Recuperación de datos',recovery)
                    window.settings_page.backup_page.automatic_backup()
                    window.offer_inventory_setup()
                QTimer.singleShot(0,startup)
                result=application.exec()
            finally:
                repository.close()
            if pending_restore:
                apply_restore(guard.database_path,preferences.apply)
                QMessageBox.information(None,'Respaldo restaurado','Se restauraron los datos y documentos. Vuelve a abrir Nimbo para continuar. La copia del estado anterior está en la carpeta Respaldos de tus datos.')
            return result
    except InstanceAlreadyRunning as error:
        QMessageBox.information(None, 'Nimbo ya está abierto', str(error))
        return 0
    except (InstanceLockError, StorageError, BackupError, OSError) as error:
        QMessageBox.critical(None, 'No se pudo abrir Nimbo', f'{error}\n\nCarpeta de datos: {directory}')
        return 1
