"""Read-only expense document from a single filtered snapshot."""
from datetime import date, datetime
from html import escape
from .report_format import filter_description
from .style import format_cop


def build_expenses_report(rows, filters, date_basis='spent'):
    rows = list(rows)
    active = [r for r in rows if not r['cancelled']]
    total = sum(r['amount_cents'] for r in active)
    paid = sum(r['amount_cents'] for r in active if r['paid'])
    categories = {}
    for r in active:
        categories[r['category']] = categories.get(r['category'], 0) + r['amount_cents']
    category_rows = ''.join(
        f'<tr><td>{escape(name)}</td><td align="right">{format_cop(value)}</td></tr>'
        for name, value in sorted(categories.items(), key=lambda item: -item[1]))
    detail = []
    for r in rows:
        state = ('Anulado' if r['cancelled'] else 'Cargado a tarjeta' if r['origin']=='card'
                 else 'Pagado' if r['paid'] else 'Pendiente')
        day = r['paid_on'] if date_basis=='paid' else r['spent_on']
        concept = escape(r['concept'])
        if r.get('detail'):
            concept += '<br><span class="muted">' + escape(r['detail']) + '</span>'
        if r.get('estimated'):
            concept += '<br><span class="muted">Importe estimado</span>'
        values = [date.fromisoformat(day).strftime('%d/%m/%Y') if day else '—', concept,
                  escape(r['category']), escape(r['account']), state, format_cop(r['amount_cents'])]
        detail.append('<tr>'+''.join(f'<td{chr(32)+"align=right" if i==5 else ""}>{v}</td>' for i,v in enumerate(values))+'</tr>')
    metadata = filter_description(filters)
    estimated = 'Incluye comisiones estimadas.' if any(r.get('estimated') for r in active) else ''
    return f'''<html><head><style>
    body {{font-family:sans-serif;font-size:10pt;color:#162e50;}}
    h1 {{color:#2458da;font-size:22pt;}} h2 {{font-size:14pt;}}
    th {{background:#eaf0ff;}} td {{border-bottom:1px solid #e3e8f0;}}
    .muted {{color:#64748b;}}
    .metric b {{font-size:16pt;}}
    </style></head><body><h1>Nimbo · Informe de gastos</h1>
    <p>{metadata}<br><span class="muted">Generado: {datetime.now():%d/%m/%Y %H:%M} · Moneda: COP</span></p>
    <table width="100%" cellspacing="0" cellpadding="9"><tr>
    <td class="metric" style="color:#162e50" bgcolor="#f6f8fd">Total vigente<br><b>{format_cop(total)}</b></td>
    <td class="metric" style="color:#127143" bgcolor="#f6f8fd">Pagado / cargado a tarjeta<br><b>{format_cop(paid)}</b></td>
    <td class="metric" style="color:#925900" bgcolor="#f6f8fd">Pendiente<br><b>{format_cop(total-paid)}</b></td></tr></table>
    <p class="muted">{estimated} Los anulados no suman. Los cargos a tarjeta son deuda, no salida de efectivo.
    El capital de préstamos no es gasto; se incluyen sus intereses registrados.
    Comisiones y envíos procedentes de ventas se incluyen una sola vez.</p>
    <h2>Por categoría</h2><table width="100%" cellspacing="0" cellpadding="6">
    <thead><tr><th>Categoría</th><th>Valor · COP</th></tr></thead>{category_rows}</table>
    <h2>Detalle · {len(rows)} registros ({len(active)} vigentes)</h2>
    <table width="100%" cellspacing="0" cellpadding="6"><thead><tr>
    <th width="11%">{'Pago' if date_basis=='paid' else 'Fecha del gasto'}</th>
    <th width="30%">Concepto / origen</th><th width="18%">Categoría</th>
    <th width="14%">Cuenta</th><th width="13%">Estado</th><th width="14%">Valor · COP</th>
    </tr></thead>{''.join(detail) or '<tr><td colspan="6">Sin gastos para estos filtros.</td></tr>'}</table>
    </body></html>'''
