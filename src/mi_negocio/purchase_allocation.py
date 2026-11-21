"""Asignaciones manuales COP y seguimiento de conceptos, sin inventario."""
from .purchases import line_original_total, line_vat_cop, line_base_cop, apply_invoice_vat
from decimal import Decimal, localcontext
from .purchases import CATEGORIES, convert_to_cop, categories_for, cost_states_complete

ALLOCATION_FIELDS = dict(zip(CATEGORIES, ('shipping_allocated_cents', 'importation_allocated_cents',
                                         'taxes_allocated_cents', 'other_allocated_cents')))


def allocation_summary(draft):
    registered = {key: sum(convert_to_cop(c.amount_cents,c.currency,c.exchange_rate)
                          for c in draft.costs if c.category == key) for key in categories_for(draft)}
    assigned = {key:sum(getattr(line,ALLOCATION_FIELDS[key]) if key in ALLOCATION_FIELDS else line.extra_allocations.get(key,0) for line in draft.lines) for key in categories_for(draft)}
    remaining = {key: registered[key]-assigned[key] for key in categories_for(draft)}
    return dict(registered=registered,assigned=assigned,remaining=remaining,complete=all(v == 0 for v in remaining.values()))


def line_unit_costs(line):
    base=line_base_cop(line)
    total=base+line_vat_cop(line)+sum(getattr(line,field) for field in ALLOCATION_FIELDS.values())+sum(line.extra_allocations.values())
    with localcontext() as context:
        context.prec=60
        return dict(purchase_cents=Decimal(base)/line.quantity,landed_cents=Decimal(total)/line.quantity,
                    approximate=bool(base % line.quantity or total % line.quantity))


def purchase_progress(draft, cancelled=False):
    pending=[key for key in categories_for(draft) if draft.cost_states and draft.cost_states[key]=='pending']
    unselected=[key for key in categories_for(draft) if draft.cost_states and draft.cost_states[key]=='unselected']
    complete=draft.costs_complete if draft.cost_states is None else cost_states_complete(draft.cost_states)
    state=('cancelled' if cancelled else 'costs_pending' if not complete else
           'complete' if allocation_summary(draft)['complete'] else 'allocation_pending')
    return dict(state=state,pending_categories=pending,unselected_categories=unselected,legacy=draft.cost_states is None)


def automatic_allocations(draft):
    """For one model only, spread each registered charge by unit count in COP.

    Cumulative integer division preserves every cent even with repeated lines.
    Merchandise and per-line VAT are already priced separately and stay unchanged.
    """
    from dataclasses import replace
    from .purchases import invalid
    if not draft.lines or len({line.product_id for line in draft.lines}) != 1:
        return draft
    if any(type(line.quantity) is not int or line.quantity <= 0 for line in draft.lines):
        invalid('La cantidad debe ser un entero positivo.')
    total_quantity = sum(line.quantity for line in draft.lines)
    registered = {key: 0 for key in categories_for(draft)}
    for cost in draft.costs:
        if cost.category not in registered:
            invalid('Selecciona una categoría de costo.')
        registered[cost.category] += convert_to_cop(cost.amount_cents, cost.currency, cost.exchange_rate)
    lines = []
    offset = 0
    for line in draft.lines:
        amounts = {key: value*(offset+line.quantity)//total_quantity-value*offset//total_quantity
                   for key, value in registered.items()}
        fields = {field: amounts.get(key, 0) for key, field in ALLOCATION_FIELDS.items()}
        extras = {key: value for key, value in amounts.items() if key not in ALLOCATION_FIELDS and value}
        lines.append(replace(line, **fields, extra_allocations=extras))
        offset += line.quantity
    return replace(draft, lines=tuple(lines))
