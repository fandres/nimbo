from mi_negocio.ui.expenses_report import build_expenses_report


def row(**kw):
    return dict(dict(spent_on='2026-11-01',paid_on=None,concept='Meta <campaña>',category='Marketing',category_key='manual:1',account='—',amount_cents=10000,paid=False,cancelled=False,estimated=False,origin='manual',detail='',source_id=1),**kw)


def test_expense_totals_and_credit_are_not_cash():
    html=build_expenses_report([row(),row(amount_cents=20000,paid=True,origin='card'),row(amount_cents=90000,cancelled=True),row(amount_cents=3000,estimated=True,origin='sale',detail='Comisión estimada')], [('Período','Noviembre')])
    assert 'Total vigente<br><b>$ 330,00' in html
    assert 'Pagado / cargado a tarjeta<br><b>$ 200,00' in html
    assert 'Pendiente<br><b>$ 130,00' in html
    assert 'Cargado a tarjeta' in html and 'Incluye comisiones estimadas' in html
    assert 'Meta &lt;campaña&gt;' in html and 'Anulado' in html


def test_empty_report_escapes_filters():
    html=build_expenses_report([], [('Búsqueda','<img src="file:///tmp/a">')])
    assert 'Sin gastos para estos filtros' in html
    assert '<img' not in html


def test_paid_date_and_cancelled_only():
    html=build_expenses_report([row(cancelled=True,paid_on='2026-11-03')], [], 'paid')
    assert '03/11/2026' in html and 'Total vigente<br><b>$ 0,00' in html
