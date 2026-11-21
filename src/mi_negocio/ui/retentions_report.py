"""HTML snapshot for retention reporting and annual certificate follow-up."""
from datetime import date,datetime
from html import escape
from ..retention_certificates import STATUSES
from .report_format import filter_description
from .style import format_cop


def build_retentions_report(groups,filters):
    groups=list(groups)
    metadata = filter_description(filters)
    total=sum(g['withholding_cents'] for g in groups)
    booked=sum(g['booked_cents'] for g in groups)
    historical=sum(g['informative_cents'] for g in groups)
    pending=sum(g['status']!='received' for g in groups)
    body=[];detail=[]
    for g in groups:
        identity=escape(g['identification']) if not g['missing_identification'] else '<b>Sin cédula / NIT: revisar identidad</b>'
        values=[str(g['year']),escape(g['name'])+'<br>'+identity,str(len(g['sales'])),
                escape(STATUSES[g['status']]),format_cop(g['withholding_cents'])]
        body.append('<tr>'+''.join('<td>'+v+'</td>' for v in values)+'</tr>')
        if g['note']:body.append('<tr><td colspan="5" class="muted">Nota: '+escape(g['note'])+'</td></tr>')
        for sale in g['sales']:
            treatment=('Informativa histórica' if not sale['withholding_deducted'] else
                       'Registrada al cobrar' if sale['received'] else 'Pendiente de cobro')
            values=[date.fromisoformat(sale['sold_on']).strftime('%d/%m/%Y'),
                    escape(sale['customer_name'])+'<br>'+escape(sale['customer_identification'] or 'Sin documento'),
                    escape(sale['customer_email'] or 'Sin correo'),
                    escape(sale['invoice_ref'] or 'Sin factura')+'<br>Venta #'+str(sale['id']),
                    format_cop(sale['total_cents']),format_cop(sale['withholding_cents']),treatment]
            detail.append('<tr>'+''.join('<td>'+v+'</td>' for v in values)+'</tr>')
    if not groups:
        body.append('<tr><td colspan="5">Sin retenciones para estos filtros.</td></tr>')
        detail.append('<tr><td colspan="7">Sin facturas.</td></tr>')
    return f'''<html><head><style>
    body {{color:#162e50;font-family:sans-serif;font-size:10pt;}}
    h1 {{color:#2458da;font-size:22pt;}} h2 {{font-size:14pt;}}
    th {{background-color:#f4f6fb;}} td {{border-bottom:1px solid #e3e8f0;}}
    .muted {{color:#64748b;}}
    .metric b {{font-size:16pt;}}
    </style></head><body><h1>Nimbo · Retenciones y certificados</h1>
    <p>{metadata}<br><span class="muted">Generado: {datetime.now():%d/%m/%Y %H:%M} · COP</span></p>
    <table width="100%" cellspacing="0" cellpadding="8"><tr>
    <td class="metric" style="color:#162e50" bgcolor="#f6f8fd">Retenciones de ventas del período<br><b>{format_cop(total)}</b></td>
    <td class="metric" style="color:#127143" bgcolor="#f6f8fd">Registradas en la cuenta al cobrar<br><b>{format_cop(booked)}</b></td>
    <td class="metric" style="color:#2445b8" bgcolor="#f6f8fd">Históricas informativas<br><b>{format_cop(historical)}</b></td>
    <td class="metric" style="color:#925900" bgcolor="#f6f8fd">Certificados sin recibir<br><b>{pending}</b></td>
    </tr></table>
    <p class="muted">Solo ventas vigentes con retención. Valores calculados por Nimbo al 2,5 % del total de cada venta marcada,
    incluido el envío cobrado. La primera cifra incluye ventas pendientes de cobro y retenciones históricas informativas;
    no representa saldo disponible ni confirma el importe de un certificado.<br>
    Los importes y facturas corresponden al período filtrado. El estado del certificado corresponde al cliente y año completo.
    Una búsqueda selecciona el grupo completo del cliente/año dentro del período. Este informe no sustituye el certificado.</p>
    <h2>Seguimiento por cliente y año</h2>
    <table width="100%" cellspacing="0" cellpadding="6"><thead><tr>
    <th width="8%">Año</th><th width="40%">Cliente / identificación</th><th width="10%">Ventas</th>
    <th width="25%">Certificado anual</th><th width="17%">Retención del período</th>
    </tr></thead>{''.join(body)}</table>
    <h2>Facturas del período</h2>
    <table width="100%" cellspacing="0" cellpadding="6"><thead><tr>
    <th width="10%">Fecha</th><th width="21%">Cliente / identificación</th><th width="22%">Correo</th>
    <th width="10%">Factura</th><th width="12%">Venta · COP</th><th width="12%">Retención · COP</th><th width="13%">Tratamiento</th>
    </tr></thead>{''.join(detail)}</table>
    <p class="muted">Sin identificación, se agrupa por nombre normalizado. Completa la cédula o NIT en la venta para distinguir personas con nombres iguales.
    Al corregir la identificación se crea otro grupo; su seguimiento comienza pendiente y no se traslada automáticamente.</p>
    </body></html>'''
