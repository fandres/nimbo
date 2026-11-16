"""Collect distribution notices and record the Debian libraries shipped in a bundle."""
import json
from pathlib import Path
import shutil
import subprocess
import sys


def collect(bundle, root):
    destination = bundle / 'third-party-licenses'
    shutil.copytree(root / 'docs/releases/third-party-licenses', destination, dirs_exist_ok=True)
    packages = {}
    if sys.platform == 'linux':
        for library in (bundle / '_internal').glob('*.so*'):
            result = subprocess.run(['dpkg-query', '-S', '*/' + library.name], text=True, capture_output=True)
            for line in result.stdout.splitlines():
                package = line.split(': /')[0]
                if package in packages:
                    continue
                result = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\t${source:Package}\t${source:Version}', package], text=True, capture_output=True)
                if result.returncode:
                    continue
                binary, source, version = result.stdout.split('\t')
                packages[package] = dict(binary=binary, source=source, version=version)
                copyright_file = Path('/usr/share/doc') / binary.split(':')[0] / 'copyright'
                if copyright_file.exists():
                    target = destination / 'Debian' / binary.replace(':', '_') / 'copyright'
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(copyright_file, target)
    files = sorted(str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file() and ('.so' in p.name or p.suffix.lower() in ('.dll', '.pyd')))
    (bundle / 'bundled-libraries.json').write_text(json.dumps(files, indent=2))
    (bundle / 'debian-library-sources.json').write_text(json.dumps(list(packages.values()), indent=2))
    (root / 'dist' / ('license-inventory-' + sys.platform + '.json')).write_text(json.dumps(list(packages.values()), indent=2))
