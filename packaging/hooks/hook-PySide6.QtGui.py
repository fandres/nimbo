"""Collect Qt GUI without unused PDF and GPL-only virtual-keyboard plugins."""
from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries
            if not any(name in Path(source).name.lower() for name in ('qpdf', 'virtualkeyboard'))]
