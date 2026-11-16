"""Sales report from the exact filtered screen snapshot, without changing records."""
from datetime import date, datetime
from html import escape
from .style import format_cop


def build_sales_report(rows, filters):
    rows = list(rows)
    active = [row for row in rows if not row['cancelled_at']]
    total = sum(row['total_cents'] for row in active)
    vat = sum(row.get('vat_cents',0) for row in active)
    received = sum(row['total_cents'] for row in active if row['received'])
    retained = sum(row['withholding_cents'] for row in active if row['has_withholding'])
    metadata = '<br>'.join(f'<b>{escape(label)}:</b> {escape(value)}' for label, value in filters)
    body = []
    for row in rows:
        state = 'Anulada' if row['cancelled_at'] else 'Recibido' if row['received'] else 'Pendiente'
        customer = escape(row['customer_name'] or 'Sin nombre')
        customer += '<br><span style="color:#64748b">Cédula / NIT: ' + escape(row['customer_identification'] or 'Sin registrar') + '</span>'
        payment = escape(row['method_name']) + '<br>' + escape(row['account_name'])
        amount = format_cop(row['total_cents'])
        if row.get('vat_enabled'):
            amount += '<br><span class="muted">IVA: ' + format_cop(row.get('vat_cents',0)) + '</span>'
        values = [date.fromisoformat(row['sold_on']).strftime('%d/%m/%Y'), customer,
                  escape(row['invoice_ref'] or 'Sin factura') + '<br>Venta #' + str(row['id']),
                  payment, state, amount,
                  format_cop(row['withholding_cents']) if row['has_withholding'] else 'No aplica']
        cells = ''.join(f'<td align="{"right" if i >= 5 else "left"}">{value}</td>' for i, value in enumerate(values))
        body.append('<tr' + (' bgcolor="#edf0f5"' if row['cancelled_at'] else '') + '>' + cells + '</tr>')
    if not rows:
        body.append('<tr><td colspan="7">Sin ventas para estos filtros.</td></tr>')
    return f'''<html><head><style>
        body {{ color:#162e50; font-family:sans-serif; font-size:9pt; }}
        h1 {{ color:#2458da; font-size:22pt; }} h2 {{ font-size:12pt; }}
        th {{ background-color:#eaf0ff; }} td {{ border-bottom:1px solid #e3e8f0; }}
        .muted {{ color:#64748b; }}
        </style></head><body>
        <h1>Nimbo · Informe de ventas</h1><p>{metadata}<br>
        <span class="muted">Generado: {datetime.now():%d/%m/%Y %H:%M} · Moneda: COP</span></p>
        <table width="100%" cellspacing="0" cellpadding="9"><tr>
        <td bgcolor="#eaf0ff">Total vigente<br><b>{format_cop(total)}</b></td>
        <td bgcolor="#e6f5ed">Recibido bruto<br><b>{format_cop(received)}</b></td>
        <td bgcolor="#fff2e5">Por cobrar bruto<br><b>{format_cop(total-received)}</b></td>
        <td bgcolor="#edf0fa">Retenciones<br><b>{format_cop(retained)}</b></td>
        </tr></table>
        <p>IVA incluido en los totales vigentes: <b>{format_cop(vat)}</b></p>
        <p class="muted">Los totales excluyen ventas anuladas. Importes brutos: incluyen envío cobrado;
        no descuentan comisiones ni costos y no representan depósitos bancarios ni utilidad.<br>
        Retención: 2,5 % del total de cada venta marcada, incluido envío cobrado.
        En ventas nuevas reduce el depósito; las ventas anteriores conservan el tratamiento informativo.
        Los totales brutos de este informe no descuentan retención. Este informe no sustituye el certificado de retención.</p>
        <h2>Detalle · {len(rows)} ventas ({len(active)} vigentes)</h2>
        <table width="100%" cellspacing="0" cellpadding="6"><thead><tr>
        <th width="10%">Fecha</th><th width="24%">Cliente / identificación</th>
        <th width="11%">Factura</th><th width="20%">Forma de pago / cuenta</th>
        <th width="9%">Estado</th><th width="14%">Total · COP</th><th width="12%">Retención · COP</th>
        </tr></thead>{''.join(body)}</table>
        <p class="muted">Las filas anuladas se conservan para consulta; su total y retención no suman al resumen.</p>
        </body></html>'''
