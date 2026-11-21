"""Explicitly separate unposted estimates from official report totals."""
from html import escape
from decimal import Decimal
from ..quick_entries import QuickEntriesRepository, day, yes
from ..sales import money, SaleLineInput, calculate_totals
from ..catalog import ValidationError
from .style import format_cop


def provisional_amount(kind,p):
    try:
        amount=money(p.get('amount',''))
        if kind=='expenses':return amount
        quantity=int(p.get('quantity',''))
        if quantity<=0:return None
        mode=p.get('vat','').casefold()
        if mode not in ('no aplica','sumar iva','iva incluido'):return None
        total=calculate_totals((SaleLineInput(1,quantity,amount),),0,0,Decimal(0),0,
            vat_enabled=mode!='no aplica',vat_rate=Decimal(p.get('rate','19')) if mode!='no aplica' else Decimal(19),vat_included=mode=='iva incluido')
        return total.total_cents
    except (ValueError,ArithmeticError,ValidationError):return None


def provisional_section(connection,kind,start,end,query='',account=None,paid=None,cancelled=False,withholding=None,category=None,platform=None,date_basis='spent'):
    repo=QuickEntriesRepository(connection)
    if not repo.include_provisional() or cancelled is True or platform is not None:return ''
    account_row=connection.execute('SELECT name FROM accounts WHERE id=?',(account,)).fetchone() if account else None
    category_name=None
    if category:
        if not category.startswith('manual:'):return ''
        category_row=connection.execute('SELECT name FROM expense_categories WHERE id=?',(category.split(':',1)[1],)).fetchone()
        if not category_row:return ''
        category_name=category_row[0]
    rows=[];undated=0
    for row in repo.pending(kind):
        p=row['payload']
        if query and query.casefold() not in ' '.join(p.values()).casefold():continue
        if account and (not account_row or p.get('account','').casefold() not in (str(account),account_row[0].casefold())):continue
        if category_name and p.get('category','').casefold() not in (category_name.casefold(),category.split(':',1)[1]):continue
        try:
            if paid is not None and yes(p.get('paid',''))!=paid:continue
            if withholding is not None and yes(p.get('withholding',''))!=withholding:continue
        except ValueError:continue
        try:when=day(p.get('paid_on' if date_basis=='paid' else 'date',''))
        except ValueError:undated+=1;continue
        if when<start or when>end:continue
        amount=provisional_amount(kind,p)
        rows.append((when,p.get('customer',p.get('concept','')) or 'Sin nombre',amount,row['error']))
    if not rows and not undated:return ''
    known=sum(r[2] for r in rows if r[2] is not None)
    html='<h2>Ingreso rápido · Pendientes provisionales</h2><p>Importes sin confirmar, fuera de los totales del informe. No representan cobros, pagos ni movimientos de inventario.</p>'
    html+=f'<p>{len(rows)} filas del período · Importe conocido: <b>{format_cop(known)}</b>. Las filas sin importe calculable muestran —.</p>'
    if undated:html+=f'<p>{undated} filas sin fecha válida no se asignaron al período ni se sumaron.</p>'
    html+='<table width="100%"><tr><th>Fecha</th><th>Cliente / concepto</th><th>Provisional · COP</th><th>Por completar</th></tr>'
    for when,name,amount,error in rows:
        html+='<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in (when.strftime('%d/%m/%Y'),name,format_cop(amount) if amount is not None else '—',error))+'</tr>'
    return html+'</table>'
