"""Compact, escaped filter descriptions shared by printable reports."""
from html import escape


def filter_description(filters):
    filters=list(filters)
    period='<br>'.join(f'<b>{escape(label)}:</b> {escape(value)}' for label,value in filters if label=='Período')
    details=' · '.join(f'{escape(label)}: {escape(value)}' for label,value in filters if label!='Período')
    return period+('<br><span class="muted">'+details+'</span>' if details else '')
