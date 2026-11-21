"""Bundled product identity, separate from the user's business logo."""
from pathlib import Path
from PySide6.QtGui import QIcon


def app_icon():
    return QIcon(str(Path(__file__).parent/'assets'/'nimbo.svg'))
