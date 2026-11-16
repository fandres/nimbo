import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QTimer, QStandardPaths
from PySide6.QtWidgets import QMessageBox

from mi_negocio import app
from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository
from mi_negocio.ui.main_window import MainWindow


def test_external_data_path_survives_working_directory_change(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'datos personales'))
    app.configure_identity(qapp)
    directory = app.data_directory()
    if sys.platform == 'win32':
        # Qt uses Windows known folders, not XDG_DATA_HOME. Check the real path
        # without writing there, then isolate database IO in this test's folder.
        assert directory == Path(os.environ['APPDATA']) / 'Fandres' / 'MiNegocio'
        monkeypatch.chdir(tmp_path)
        assert app.data_directory() == directory
        directory = tmp_path / 'datos personales' / 'Fandres' / 'MiNegocio'
        monkeypatch.setattr(QStandardPaths, 'writableLocation', lambda location: str(directory))
    else:
        assert directory.is_relative_to(tmp_path / 'datos personales')
    repository = CatalogRepository(directory / 'catalog.sqlite3')
    repository.create(validate_product(ProductInput('010', 'Impresora', 'product', '0')))
    repository.close()
    monkeypatch.chdir(tmp_path)
    assert app.data_directory() == directory
    repository = CatalogRepository(directory / 'catalog.sqlite3')
    assert repository.list_products()[0].code == '010'
    repository.close()


def test_missing_or_invalid_logo_does_not_prevent_opening(qtbot, tmp_path):
    repository = CatalogRepository(tmp_path / 'logo.sqlite3')
    for path in [tmp_path / 'missing.png', tmp_path / 'bad.png']:
        if path.name == 'bad.png':
            path.write_text('not an image')
        window = MainWindow(repository, path)
        qtbot.addWidget(window)
        window.resize(800, 560)
        window.show()
        assert window.pages.currentWidget() is window.home_page
        window.navigate('catalog')
        assert window.catalog_page.new_button.isEnabled()
        assert window.catalog_page.empty_new.isVisible()
        window.close()
    repository.close()


def test_open_failure_is_reported_without_success(qapp, tmp_path, monkeypatch):
    blocked = tmp_path / 'file'
    blocked.write_text('keep')
    monkeypatch.setattr(app, 'data_directory', lambda: blocked / 'Fandres' / 'MiNegocio')
    messages = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda parent, title, message: messages.append(message))
    assert app.main() == 1
    assert messages
    assert blocked.read_text() == 'keep'


def test_startup_and_shutdown_in_separate_process(tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_DATA_HOME=str(tmp_path / 'fresh data'),
               PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'),
               NIMBO_TEST_DATA=str(tmp_path / 'fresh data'))
    result = subprocess.run([sys.executable, '-c',
        'from PySide6.QtWidgets import QApplication; from PySide6.QtCore import QTimer, QStandardPaths; '
        'import os; from pathlib import Path; from mi_negocio import app; '
        'app.data_directory=lambda: Path(os.environ["NIMBO_TEST_DATA"]); '
        'a=QApplication([]); QTimer.singleShot(100,a.quit); raise SystemExit(app.main())'],
        env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert list((tmp_path / 'fresh data').rglob('catalog.sqlite3'))


def test_nimbo_name_preserves_storage_identity(qapp,tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path))
    app.configure_identity(qapp)
    assert qapp.applicationDisplayName()=='Nimbo'
    assert qapp.applicationVersion()=='0.5.0b1'
    root = Path(os.environ['APPDATA']) if sys.platform == 'win32' else tmp_path
    assert app.data_directory() == root / 'Fandres' / 'MiNegocio'


def test_packaged_smoke_command_does_not_create_user_database(tmp_path):
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_DATA_HOME=str(tmp_path/'user-data'),
             PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    result=subprocess.run([sys.executable, '-c',
        'from mi_negocio import app; '
        'app.data_directory=lambda: (_ for _ in ()).throw(AssertionError("Persistent path accessed")); '
        'import sys; sys.argv=["nimbo", "--smoke-test"]; raise SystemExit(app.main())'],env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert not list(tmp_path.rglob('catalog.sqlite3'))


def test_second_instance_does_not_open_database(qapp,tmp_path,monkeypatch):
    from mi_negocio.instance_lock import DatabaseInstanceLock
    monkeypatch.setattr(app,'data_directory',lambda:tmp_path)
    notices=[];monkeypatch.setattr(QMessageBox,'information',lambda *args:notices.append(args[2]))
    def forbidden(*args,**kwargs):raise AssertionError('Second instance touched SQLite')
    monkeypatch.setattr(app,'CatalogRepository',forbidden)
    with DatabaseInstanceLock(tmp_path/'catalog.sqlite3'):
        assert app.main()==0
    assert notices and 'abierto' in notices[0]
    assert not (tmp_path/'catalog.sqlite3').exists()


def test_database_open_error_releases_instance_lock(qapp,tmp_path,monkeypatch):
    from mi_negocio.instance_lock import DatabaseInstanceLock
    from mi_negocio.storage import StorageError
    monkeypatch.setattr(app,'data_directory',lambda:tmp_path)
    monkeypatch.setattr(QMessageBox,'critical',lambda *args:None)
    def fail(*args,**kwargs):raise StorageError('Error de prueba')
    monkeypatch.setattr(app,'CatalogRepository',fail)
    assert app.main()==1
    with DatabaseInstanceLock(tmp_path/'catalog.sqlite3'):pass


def test_window_creation_error_closes_repository_before_unlock(qapp,tmp_path,monkeypatch):
    import pytest
    from mi_negocio.instance_lock import DatabaseInstanceLock,InstanceAlreadyRunning
    monkeypatch.setattr(app,'data_directory',lambda:tmp_path)
    events=[]
    class Repository:
        def __init__(self,*args):events.append('opened')
        def close(self):
            with pytest.raises(InstanceAlreadyRunning):DatabaseInstanceLock(tmp_path/'catalog.sqlite3').acquire()
            events.append('closed')
    def fail(*args):raise RuntimeError('Window failed')
    monkeypatch.setattr(app,'CatalogRepository',Repository);monkeypatch.setattr(app,'MainWindow',fail)
    with pytest.raises(RuntimeError,match='Window failed'):app.main()
    assert events==['opened','closed']
    with DatabaseInstanceLock(tmp_path/'catalog.sqlite3'):pass
