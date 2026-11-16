import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from mi_negocio.instance_lock import DatabaseInstanceLock, InstanceAlreadyRunning, InstanceLockError


def env():
    return dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'),QT_QPA_PLATFORM='offscreen')


def test_same_database_blocks_and_distinct_database_is_independent(qapp,tmp_path):
    path=tmp_path/'new'/'catalog.sqlite3'
    first=DatabaseInstanceLock(path);first.acquire()
    try:
        assert not path.exists()
        assert first.lock_path.exists()
        second=DatabaseInstanceLock(path)
        with pytest.raises(InstanceAlreadyRunning):second.acquire()
        second.release()  # Must never release the other owner's lock.
        with pytest.raises(InstanceAlreadyRunning):second.acquire()
        with DatabaseInstanceLock(tmp_path/'other.sqlite3'):pass
    finally:first.release()
    with DatabaseInstanceLock(path):pass
    assert not first.lock_path.exists()


def test_old_lock_for_live_process_is_not_stolen(qapp,tmp_path):
    with DatabaseInstanceLock(tmp_path/'db') as owner:
        os.utime(owner.lock_path,(1,1))
        with pytest.raises(InstanceAlreadyRunning):DatabaseInstanceLock(tmp_path/'db').acquire()
        assert owner.lock_path.exists()


def test_relative_and_symbolic_paths_share_lock(qapp,tmp_path,monkeypatch):
    folder=tmp_path/'real';folder.mkdir();alias=tmp_path/'alias'
    try:alias.symlink_to(folder,target_is_directory=True)
    except OSError:pytest.skip('This Windows environment does not grant symlink creation')
    monkeypatch.chdir(tmp_path)
    with DatabaseInstanceLock(folder/'db') as owner:
        other=DatabaseInstanceLock(Path('alias')/'db')
        assert other.database_path==owner.database_path
        with pytest.raises(InstanceAlreadyRunning):other.acquire()


def test_invalid_parent_never_creates_database(qapp,tmp_path):
    blocked=tmp_path/'file';blocked.write_text('keep')
    with pytest.raises(InstanceLockError):
        with DatabaseInstanceLock(blocked/'db'):pass
    assert blocked.read_text()=='keep'


def test_crashed_process_lock_can_be_recovered(qapp,tmp_path):
    path=tmp_path/'db'
    code='''import os,sys
from PySide6.QtCore import QCoreApplication
from mi_negocio.instance_lock import DatabaseInstanceLock
app=QCoreApplication([])
lock=DatabaseInstanceLock(sys.argv[1]);lock.acquire()
os._exit(0)
'''
    result=subprocess.run([sys.executable,'-c',code,str(path)],env=env(),capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    guard=DatabaseInstanceLock(path);assert guard.lock_path.exists()
    with guard:assert guard.lock_path.exists()
    assert not guard.lock_path.exists()


def test_two_simultaneous_processes_only_one_wins(tmp_path):
    code='''import sys,time
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from mi_negocio.instance_lock import DatabaseInstanceLock,InstanceAlreadyRunning
app=QCoreApplication([]);root=Path(sys.argv[1]);key=sys.argv[2]
(root/('ready'+key)).write_text('ready')
deadline=time.monotonic()+15
while not (root/'go').exists():
    if time.monotonic()>deadline:raise SystemExit(3)
    time.sleep(.01)
guard=DatabaseInstanceLock(root/'db')
try:
    guard.acquire();result='acquired'
except InstanceAlreadyRunning:result='busy'
(root/('result'+key)).write_text(result)
while not (root/'release').exists():
    if time.monotonic()>deadline:raise SystemExit(4)
    time.sleep(.01)
guard.release()
'''
    children=[subprocess.Popen([sys.executable,'-c',code,str(tmp_path),str(i)],env=env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)]
    def wait_files(prefix):
        deadline=time.monotonic()+10
        while not all((tmp_path/(prefix+str(i))).exists() for i in range(2)):
            assert time.monotonic()<deadline,'Child did not reach '+prefix
            time.sleep(.01)
    try:
        wait_files('ready');(tmp_path/'go').touch();wait_files('result')
        assert sorted((tmp_path/('result'+str(i))).read_text() for i in range(2))==['acquired','busy']
        (tmp_path/'release').touch()
        for child in children:
            out,error=child.communicate(timeout=10);assert child.returncode==0,error
    finally:
        for child in children:
            if child.poll() is None:child.kill();child.communicate()
