"""Purchase report from stored amounts; never infer VAT from generic taxes."""
from collections import defaultdict
from datetime import date, datetime
from html import escape
from ..purchases import is_vat_cost
from .report_format import filter_description
from .style import format_cop


def manual_vat(row, cost):
    name=row['cost_definitions'].get(cost['category'],{}).get('name','')
    return is_vat_cost(name,cost['description'])


def purchase_breakdown(row):
    base=sum(line['subtotal_cents'] for line in row['lines'])
    vat=sum(line.get('vat_cents',0) for line in row['lines'])
    vat+=sum(cost['subtotal_cents'] for cost in row['costs'] if manual_vat(row,cost))
    other=sum(cost['subtotal_cents'] for cost in row['costs'] if not manual_vat(row,cost))
    return dict(base=base,vat=vat,other=other,total=base+vat+other)


def build_purchases_report(rows,filters):
    rows=list(rows)
    active=[row for row in rows if not row['cancelled_at']]
    totals=dict(base=0,vat=0,other=0,total=0)
    concepts=defaultdict(int)
    for row in active:
        for key,value in purchase_breakdown(row).items():totals[key]+=value
        for cost in row['costs']:
            if not manual_vat(row,cost):
                name=row['cost_definitions'].get(cost['category'],{}).get('name',cost['category'])
                concepts[name]+=cost['subtotal_cents']
    metadata = filter_description(filters)
    summary=''.join(f'<td class="metric" bgcolor="#f6f8fd">{title}<br><b>{format_cop(totals[key])}</b></td>'
        for key,title,color in [('base','Base de mercancía','#eaf0ff'),('vat','IVA registrado','#edf0fa'),
                                ('other','Otros costos','#fff2e5'),('total','Total registrado','#e6f5ed')])
    body=[]
    for row in rows:
        amounts=purchase_breakdown(row)
        supplier=escape(row['supplier'])
        if row.get('supplier_alias'):supplier+='<br>'+escape(row['supplier_alias'])
        state='Anulada' if row['cancelled_at'] else 'Vigente'
        mode=('IVA del total · '+escape(row['invoice_vat_rate'])+' %' if row.get('invoice_vat_enabled') else
              'IVA por producto' if any(l.get('vat_enabled') for l in row['lines']) else
              'IVA como cargo' if amounts['vat'] else 'Sin IVA discriminado')
        values=[f"{date.fromisoformat(row['purchased_on']):%d/%m/%Y}<br>Compra #{row['id']}",
                supplier+'<br>'+escape(row['reference'] or 'Sin referencia'),state+'<br>'+mode]
        values += [format_cop(amounts[k]) for k in ('base','vat','other','total')]
        body.append('<tr'+(' bgcolor="#edf0f5"' if row['cancelled_at'] else '')+'>'+''.join(
            f'<td align="{"right" if i>=3 else "left"}">{value}</td>' for i,value in enumerate(values))+'</tr>')
    if not rows:body.append('<tr><td colspan="7">Sin compras para estos filtros.</td></tr>')
    costs=''.join(f'<tr><td>{escape(name)}</td><td align="right">{format_cop(value)}</td></tr>' for name,value in sorted(concepts.items()))
    if not costs:costs='<tr><td colspan="2">Sin otros costos registrados.</td></tr>'
    return f'''<html><head><style>
    body {{color:#162e50;font-family:sans-serif;font-size:10pt;}}
    h1 {{color:#2458da;font-size:22pt;}} h2 {{font-size:14pt;}}
    th {{background-color:#f4f6fb;}} td {{border-bottom:1px solid #e3e8f0;}}
    .muted {{color:#64748b;}}
    .metric b {{font-size:16pt;}}
    </style></head><body><h1>Nimbo · Informe de compras</h1>
    <p>{metadata}<br><span class="muted">Generado: {datetime.now():%d/%m/%Y %H:%M} · Moneda: COP</span></p>
    <table width="100%" cellspacing="0" cellpadding="8"><tr>{summary}</tr></table>
    <p class="muted">Importes registrados: no confirman pagos. Pueden incluir costos provisionales.
    Los totales excluyen compras anuladas. Base + IVA + otros costos = total registrado.<br>
    Se desglosa el IVA por producto, separado del total o identificado como cargo de IVA.
    No se estima IVA dentro de conceptos genéricos como Impuestos.</p>
    <h2>Detalle · {len(rows)} compras ({len(active)} vigentes)</h2>
    <table width="100%" cellspacing="0" cellpadding="6"><thead><tr>
    <th width="12%">Fecha / compra</th><th width="22%">Proveedor / referencia</th><th width="14%">Estado / IVA</th>
    <th width="13%">Base · COP</th><th width="13%">IVA · COP</th><th width="13%">Otros · COP</th><th width="13%">Total · COP</th>
    </tr></thead>{''.join(body)}</table>
    <h2>Otros costos por concepto · compras vigentes</h2>
    <table width="100%" cellspacing="0" cellpadding="6"><thead><tr><th>Concepto</th><th>Importe · COP</th></tr></thead>{costs}</table>
    <p class="muted">Los cargos de IVA se incluyen únicamente en la columna IVA. Las filas anuladas no suman al resumen ni al desglose por concepto.</p>
    </body></html>'''
