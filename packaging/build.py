"""Build native release packages. Does not download tools or access business data."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collect_licenses import collect

ROOT = Path(__file__).resolve().parents[1]


def run(command, **kwargs):
    subprocess.run([str(part) for part in command], check=True, **kwargs)


def target():
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        raise SystemExit('This release targets x86-64 only.')
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux':
        release = platform.freedesktop_os_release()
        if release.get('ID') != 'debian' or release.get('VERSION_ID') != '13':
            raise SystemExit('Build the Linux package on Debian 13, not on the development host.')
        return 'linux'
    raise SystemExit('Build on Debian 13 or Windows 11.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--appimagetool', type=Path, help='Local appimagetool executable (Linux only)')
    parser.add_argument('--runtime', type=Path, help='Local x86-64 AppImage type-2 runtime (Linux only)')
    parser.add_argument('--execution-environment', choices=('native', 'wine'), default='native',
                        help='Record whether Windows tools ran on Windows or through Wine')
    args = parser.parse_args()
    system = target()
    if sys.version_info[:2] != (3, 13):
        raise SystemExit('Use Python 3.13 for these release recipes.')
    for name, version in [('PySide6', '6.12.0'), ('PyInstaller', '6.22.3')]:
        if importlib.metadata.version(name) != version:
            raise SystemExit(f'Install packaging/requirements.txt: {name} must be {version}.')
    if system == 'linux':
        if not args.appimagetool or not args.appimagetool.is_file() or not args.runtime or not args.runtime.is_file():
            raise SystemExit('Provide --appimagetool and --runtime paths; see docs/releases/nimbo-alpha.md.')
        args.appimagetool = args.appimagetool.resolve()
        args.runtime = args.runtime.resolve()
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version'].replace('a1', '-alpha.1').replace('b1', '-beta.1')
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    basename = f'Nimbo-{version}-{system}-x86_64'
    artifact = output / (basename + ('.AppImage' if system == 'linux' else '.zip'))
    if artifact.exists():
        raise SystemExit(f'Refusing to overwrite {artifact}; move it first.')
    with tempfile.TemporaryDirectory(prefix='nimbo-build-') as temporary:
        work = Path(temporary)
        run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
             '--additional-hooks-dir', ROOT / 'packaging/hooks',
             '--exclude-module', 'readline',
             '--windowed', '--name', 'Nimbo', '--paths', ROOT / 'src',
             '--distpath', work / 'dist', '--workpath', work / 'work', '--specpath', work,
             ROOT / 'packaging/entry.py'])
        bundle = work / 'dist/Nimbo'
        executable = bundle / ('Nimbo.exe' if system == 'windows' else 'Nimbo')
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        run([executable, '--smoke-test'], env=environment, timeout=30)
        shutil.copy2(ROOT / 'docs/releases/LEEME-beta.txt', bundle)
        if system == 'windows':
            shutil.copy2(ROOT / 'docs/releases/PRUEBA-WINDOWS11.txt', bundle)
        shutil.copy2(ROOT / 'LICENSE', bundle / 'LICENSE-Nimbo-MIT.txt')
        shutil.copy2(ROOT / 'docs/releases/THIRD-PARTY-NOTICES.txt', bundle)
        shutil.copy2(ROOT / 'docs/releases/REEMPLAZAR-BIBLIOTECAS.txt', bundle)
        # Do not accidentally ship plugins/modules that Nimbo does not use.
        forbidden = [path for path in bundle.rglob('*') if path.is_file() and
                     any(name in path.name.lower() for name in ('virtualkeyboard', 'qt6pdf', 'qpdf'))]
        if forbidden:raise SystemExit('Unexpected Qt modules: '+str(forbidden))
        notices = bundle / 'third-party-licenses'
        # Include installed license/notice files rather than any local commercial data.
        for name in ('PySide6', 'PySide6-Essentials', 'PySide6-Addons', 'shiboken6', 'PyInstaller'):
            distribution = importlib.metadata.distribution(name)
            for file in distribution.files or []:
                if any(word in str(file).lower() for word in ('license', 'copying', 'notice')):
                    source = Path(distribution.locate_file(file))
                    if source.is_file():
                        destination = notices / name / str(file).replace('..', '_')
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination)
        collect(bundle, ROOT)
        if system == 'windows':
            shutil.make_archive(str(output / basename), 'zip', root_dir=bundle.parent, base_dir=bundle.name)
        else:
            appdir = work / 'Nimbo.AppDir'
            appdir.mkdir()
            shutil.copytree(bundle, appdir / 'usr')
            for asset in ('nimbo.desktop', 'nimbo.svg'):
                shutil.copy2(ROOT / 'packaging' / asset, appdir)
            launcher = appdir / 'AppRun'
            launcher.write_text('#!/bin/sh\nAPPDIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\nexec "$APPDIR/usr/Nimbo" "$@"\n')
            launcher.chmod(0o755)
            run([args.appimagetool, '--appimage-extract-and-run', '--runtime-file', args.runtime,
                 appdir, artifact], env=dict(os.environ, ARCH='x86_64'))
            run([artifact, '--appimage-extract-and-run', '--smoke-test'], env=environment, timeout=60)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.with_suffix(artifact.suffix + '.sha256').write_text(f'{digest}  {artifact.name}\n')
    freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    tools = {}
    if system == 'linux':
        tools = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in [('appimagetool', args.appimagetool), ('runtime', args.runtime)]}
    manifest = dict(version=version, target=system, architecture=platform.machine(),
                    python=platform.python_version(), build_os=platform.platform(),
                    distribution=platform.freedesktop_os_release() if system == 'linux' else {}, packages=freeze.splitlines(),
                    smoke_test='passed', execution_environment=args.execution_environment, desktop_test='pending', sha256=digest, build_tools_sha256=tools)
    artifact.with_suffix(artifact.suffix + '.json').write_text(json.dumps(manifest, indent=2))
    print(f'Built {artifact}. Real desktop testing is still required.')


if __name__ == '__main__':
    main()
