"""Grupos visuales compactos para filtros de listados."""
from PySide6.QtWidgets import QFrame,QVBoxLayout
from .sales_widgets import note


def filter_section(title,layout):
    frame=QFrame();frame.setObjectName('filterSection')
    frame.setStyleSheet('QFrame#filterSection { background: #f4f7fc; border: 1px solid #dde5f1; border-radius: 9px; }')
    box=QVBoxLayout(frame);box.setContentsMargins(10,7,10,7);box.setSpacing(5)
    box.addWidget(note(title,'fieldHeading'));box.addLayout(layout)
    return frame
