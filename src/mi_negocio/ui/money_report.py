"""Read-only money report using the same filtered movements as the screen."""
from datetime import date, datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QIODevice, QMarginsF, QSaveFile
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument, QTextOption

from .style import format_cop


def build_money_report(rows, start, end, account_name, query='', account_id=None):
    """Render an immutable list snapshot; cash totals exclude financing/internal legs."""
    if start > end:
        raise ValueError('Revisa el rango de fechas.')
    rows = list(rows)
    flow = [r for r in rows if r['account_id'] is not None and not r['is_card'] and not r.get('is_withholding',False)
            and (account_id is not None or r['kind'] != 'transfer')]
    incoming = sum(max(0, r['delta']) for r in flow)
    outgoing = sum(max(0, -r['delta']) for r in flow)
    net_background = '#e6f5ed' if incoming >= outgoing else '#fdebed'
    all_in = sum(max(0, r['delta']) for r in rows)
    all_out = sum(max(0, -r['delta']) for r in rows)
    sources = {'sale': 'Venta', 'expense': 'Gasto', 'loan': 'Préstamo',
               'money': 'Movimiento', 'card': 'Tarjeta'}
    body = []
    for row in rows:
        labels = []
        if row.get('is_withholding'):
            labels.append('Retención de renta: no es efectivo disponible')
        if row['is_card']:
            labels.append('Crédito: reduce deuda' if row['delta'] > 0 else 'Crédito: aumenta deuda')
        elif row['account_id'] is None:
            labels.append('Sin cuenta asignada')
        if row['kind'] == 'transfer':
            labels.append('Transferencia interna')
        source = sources.get(row['origin'], 'Movimiento') + ' #' + str(row['source_id'])
        concept = escape(row['concept'])
        if labels:
            concept += '<br><span style="color:#64748b">' + escape(' · '.join(labels)) + '</span>'
        values = [date.fromisoformat(row['date']).strftime('%d/%m/%Y'), concept,
                  escape(source), escape(row['account']),
                  format_cop(row['delta']) if row['delta'] > 0 else '—',
                  format_cop(-row['delta']) if row['delta'] < 0 else '—']
        cells = ''.join(f'<td align="{"right" if i >= 4 else "left"}">{value}</td>' for i, value in enumerate(values))
        body.append('<tr>' + cells + '</tr>')
    if not rows:
        body.append('<tr><td colspan="6">Sin movimientos para estos filtros.</td></tr>')
    return f'''<html><head><style>
        body {{ color:#162e50; font-family: sans-serif; font-size:10pt; }}
        h1 {{ font-size:22pt; color:#2458da; }}
        h2 {{ font-size:12pt; margin-top:16px; }}
        th {{ background-color:#eaf0ff; color:#162e50; }}
        td {{ border-bottom:1px solid #e3e8f0; }}
        .muted {{ color:#64748b; }}
        </style></head><body>
        <h1>Nimbo · Movimientos de dinero</h1>
        <p><b>Período:</b> {start:%d/%m/%Y} al {end:%d/%m/%Y}<br>
        <b>Cuenta:</b> {escape(account_name)}<br>
        <b>Búsqueda:</b> {escape(query) if query else 'Sin búsqueda'}<br>
        <span class="muted">Generado: {datetime.now():%d/%m/%Y %H:%M} · Moneda: COP</span></p>
        <h2>Flujo de efectivo del filtro</h2>
        <table width="100%" cellspacing="0" cellpadding="10"><tr>
        <td bgcolor="#eaf0ff">Entradas<br><b>{format_cop(incoming)}</b></td>
        <td bgcolor="#fff2e5">Salidas<br><b>{format_cop(outgoing)}</b></td>
        <td bgcolor="{net_background}">Flujo neto del filtro<br><b>{format_cop(incoming-outgoing)}</b></td>
        </tr></table>
        <p class="muted">Cobros y pagos registrados; no representa utilidad ni saldo disponible.
        Se excluyen del flujo las tarjetas y los movimientos sin cuenta.
        Las transferencias internas se excluyen al consultar todas las cuentas;
        en una cuenta individual sí afectan su flujo. Los cobros de ventas ya incluyen
        el descuento de la comisión real.</p>
        <h2>Detalle · {len(rows)} movimientos</h2>
        <p class="muted">En filas de crédito, Entrada significa reducción de deuda y Salida aumento de deuda.</p>
        <table width="100%" cellspacing="0" cellpadding="7" border="0">
        <thead><tr><th width="11%">Fecha</th><th width="29%">Concepto</th><th width="13%">Origen</th>
        <th width="17%">Cuenta</th><th width="15%">Entrada · COP</th><th width="15%">Salida · COP</th></tr></thead>
        {''.join(body)}</table>
        <p><b>Totales de la tabla:</b> Entradas: {format_cop(all_in)} · Salidas: {format_cop(all_out)}<br>
        <span class="muted">Incluyen transferencias y crédito; pueden diferir del flujo de efectivo.</span></p>
        </body></html>'''


def write_money_pdf(path, html, *, title='Nimbo · Movimientos de dinero'):
    """Write atomically so cancellation/failure cannot truncate an existing report."""
    output = QSaveFile(str(Path(path)))
    if not output.open(QIODevice.WriteOnly):
        raise OSError(output.errorString())
    try:
        writer = QPdfWriter(output)
        writer.setTitle(title)
        writer.setCreator('Nimbo')
        writer.setResolution(96)
        writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape,
                                        QMarginsF(12, 12, 12, 12)))
        document = QTextDocument()
        document.setDefaultFont(QFont('Sans Serif', 10))
        option = document.defaultTextOption()
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        document.setDefaultTextOption(option)
        document.setHtml(html)
        document.print_(writer)
        del writer
        if not output.commit():
            raise OSError(output.errorString())
    except Exception:
        output.cancelWriting()
        raise
