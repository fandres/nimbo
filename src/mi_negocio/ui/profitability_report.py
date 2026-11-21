"""Printable profitability snapshot with explicit missing/provisional valuation."""
from datetime import datetime
from html import escape
from .style import format_cop


def amount(value):
    return 'No disponible' if value is None else format_cop(value)


def build_profitability_report(snapshot, start, end):
    rows = snapshot['rows']
    detail = []
    for row in rows:
        state = 'Sin costo trazable' if row['cost_cents'] is None else 'Provisional' if row['provisional'] else 'Costos completos'
        color = '#a35d00' if row['cost_cents'] is None or row['provisional'] else '#087341'
        sources = ', '.join(f'Compra #{key}' for key in row['purchases']) or 'Sin compra vinculada'
        notes = escape('; '.join(row['reasons']))
        cells = [escape(row['sold_on']), f"<b>#{row['id']} · {escape(row['customer'])}</b><br>Factura: {escape(row['invoice'] or 'Sin registrar')}",
                 amount(row['income_cents']), amount(row['cost_cents']),
                 amount(row['commission_cents']+row['shipping_cents']), amount(row['margin_cents'])]
        detail.append('<tr>'+''.join(f'<td align="{("right" if i>1 else "left")}">{v}</td>' for i,v in enumerate(cells))+'</tr>')
        detail.append(f'<tr><td colspan="6"><span style="color:{color}"><b>{state}</b></span> · {sources}'
                      + (f'<br><span class="muted">{notes}</span>' if notes else '') + '</td></tr>')
    if snapshot['query']:
        warning = 'La búsqueda muestra el margen de las ventas encontradas. Limpia la búsqueda para obtener el resultado del período con sus demás gastos.'
    elif snapshot['unknown_count']:
        warning = f"{snapshot['unknown_count']} ventas sin costo trazable: el resultado completo no está disponible. Los costos conocidos se muestran como suma parcial."
    elif snapshot['provisional']:
        warning = 'Resultado provisional: incluye costos pendientes de completar o comisiones estimadas.'
    else:
        warning = 'Resultado calculado con los costos registrados. Las correcciones de compras actualizan este informe.'
    return f'''<html><head><style>
    body {{font-family:sans-serif;font-size:10pt;color:#162e50;}}
    h1 {{color:#2458da;font-size:22pt;}} h2 {{font-size:14pt;}}
    th {{background:#eaf0ff;}} td {{border-bottom:1px solid #e3e8f0;}}
    .muted {{color:#64748b;}}
    .metric b {{font-size:16pt;}}
        </style></head><body><h1>Nimbo · Rentabilidad</h1>
    <p><b>Período:</b> {start:%d/%m/%Y} al {end:%d/%m/%Y}<br>
    <b>Búsqueda:</b> {escape(snapshot['query'] or 'Todas las ventas vigentes')}<br>
    <span class="muted">Generado: {datetime.now():%d/%m/%Y %H:%M} · COP · Valoración FIFO</span></p>
    <table width="100%" cellspacing="0" cellpadding="10"><tr>
    <td class="metric" style="color:#162e50" bgcolor="#f6f8fd">Ingresos sin IVA de venta<br><b>{amount(snapshot['income_cents'])}</b></td>
    <td class="metric" style="color:#925900" bgcolor="#f6f8fd">Costo de mercancía conocido{' · parcial' if snapshot['unknown_count'] else ''}<br><b>{amount(snapshot['known_cost_cents'])}</b></td>
    <td class="metric" style="color:#127143" bgcolor="#f6f8fd">Margen tras mercancía, comisión y envío<br><b>{amount(snapshot['margin_cents'])}</b></td></tr></table>
    <p style="color:#a35d00">{warning}</p>
    <table width="100%" cellspacing="0" cellpadding="7"><tr>
    <td>Comisiones: <b>{amount(snapshot['commission_cents'])}</b><br>Envíos: <b>{amount(snapshot['shipping_cents'])}</b></td>
    <td>Otros gastos del período: <b>{amount(snapshot['expenses_cents'])}</b><br>
    Resultado del período{' · provisional' if snapshot['provisional'] else ''}: <b>{amount(snapshot['result_cents'])}</b></td></tr></table>
    <p class="muted">Resultado de gestión, no liquidación fiscal ni saldo de caja. El ingreso incluye el envío cobrado.
    El costo de mercancía incluye el IVA y los cargos registrados en compras; no determina IVA descontable.
    Las retenciones no se descuentan otra vez. Otros gastos excluye comisiones y envíos automáticos de ventas;
    incluye intereses registrados, no capital de préstamos. Servicios y existencias sin costo requieren valoración.</p>
    <h2>Detalle · {len(rows)} ventas</h2>
    <table width="100%" cellspacing="0" cellpadding="6"><thead><tr>
    <th width="10%">Fecha</th><th width="26%">Venta / cliente</th><th width="16%">Ingreso sin IVA</th>
    <th width="16%">Mercancía FIFO</th><th width="16%">Comisión + envío</th><th width="16%">Margen · COP</th>
    </tr></thead>{''.join(detail) or '<tr><td colspan="6">Sin ventas para estos filtros.</td></tr>'}</table></body></html>'''
