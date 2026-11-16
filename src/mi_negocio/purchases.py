"""Compras: importes originales y costos COP, sin movimientos de inventario."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from .catalog import ValidationError
from .vat import split_vat
from .sales import check_cents, MAX_CENTS

CATEGORIES = {'international_shipping': 'Envío internacional', 'importation': 'Nacionalización / manejo',
              'taxes': 'Impuestos', 'other': 'Otros costos'}


@dataclass(frozen=True)
class PurchaseLineInput:
    product_id: int
    quantity: int
    unit_cost_cents: int
    currency: str = 'COP'
    exchange_rate: Decimal | None = None
    converted_on: date | None = None
    line_id: int | None = None
    shipping_allocated_cents: int = 0
    importation_allocated_cents: int = 0
    taxes_allocated_cents: int = 0
    other_allocated_cents: int = 0
    total_cost_cents: int | None = None
    extra_allocations: dict[str, int] = field(default_factory=dict)
    vat_enabled: bool = False
    vat_rate: Decimal = Decimal('19')
    vat_included: bool = False


def line_entered_total(line):
    return line.total_cost_cents if line.total_cost_cents is not None else line.quantity * line.unit_cost_cents


def line_original_total(line):
    return split_vat(line_entered_total(line),line.vat_enabled,line.vat_rate,line.vat_included)[0]


def line_vat_cop(line):
    base,tax,total=split_vat(line_entered_total(line),line.vat_enabled,line.vat_rate,line.vat_included)
    return convert_to_cop(total,line.currency,line.exchange_rate)-convert_to_cop(base,line.currency,line.exchange_rate)


def is_vat_cost(name, description=''):
    import re
    return bool(re.search(r'\biva\b', name+' '+description, re.IGNORECASE))


def check_duplicate_vat(draft):
    if not any(line.vat_enabled for line in draft.lines):return
    names=categories_for(draft)
    if any(is_vat_cost(names.get(cost.category,''),cost.description) and cost.amount_cents for cost in draft.costs):
        invalid('Ya calculaste IVA en los productos. Revisa el cargo adicional de IVA para no contarlo dos veces; registra allí solo el arancel u otros cargos.')


@dataclass(frozen=True)
class PurchaseCostInput:
    category: str
    description: str
    amount_cents: int
    currency: str = 'COP'
    exchange_rate: Decimal | None = None
    converted_on: date | None = None


@dataclass(frozen=True)
class PurchaseDraft:
    purchased_on: date
    supplier: str
    reference: str
    lines: tuple[PurchaseLineInput, ...]
    costs: tuple[PurchaseCostInput, ...] = ()
    costs_complete: bool = False
    cost_states: dict[str, str] | None = None
    cost_definitions: dict | None = None
    supplier_alias: str = ''
    tracking_number: str = ''


@dataclass(frozen=True)
class PurchaseTotals:
    merchandise_cents: int
    shipping_import_cents: int
    taxes_other_cents: int
    total_cents: int
    vat_cents: int = 0


@dataclass(frozen=True)
class PurchasesFilter:
    start: date | None = None
    end: date | None = None
    query: str = ''
    costs_complete: bool | None = None
    cancelled: bool | None = False
    progress: str | None = None
    received: bool | None = None


def definitions_for(draft):
    if draft.cost_definitions is not None:
        if not isinstance(draft.cost_definitions,dict) or any(not isinstance(k,str) or not k or not isinstance(v,dict) or not isinstance(v.get('name'),str) or not v['name'].strip() or v.get('group') not in ('shipping','other') for k,v in draft.cost_definitions.items()):
            invalid('Revisa los conceptos de costos de la compra.')
        return draft.cost_definitions
    from .purchase_concepts import default_definitions
    return default_definitions()


def categories_for(draft):
    return {key:value['name'] for key,value in definitions_for(draft).items()}


def invalid(message):
    raise ValidationError({'compra': message})


def validate_rate(rate):
    if (not isinstance(rate, Decimal) or not rate.is_finite() or
            not 0 < rate <= Decimal(MAX_CENTS) or rate.as_tuple().exponent < -6):
        invalid('La tasa debe ser positiva y tener hasta seis decimales.')


def convert_to_cop(amount_cents, currency, exchange_rate):
    check_cents(amount_cents)
    if currency not in ('COP', 'USD'):
        invalid('Selecciona COP o USD.')
    if exchange_rate is not None:
        validate_rate(exchange_rate)
    if currency == 'COP':
        return amount_cents
    validate_rate(exchange_rate)
    with localcontext() as context:
        context.prec = 60
        result = int((Decimal(amount_cents) * exchange_rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    check_cents(result)
    return result


def validate_purchase(draft):
    categories=categories_for(draft)
    if not isinstance(draft.tracking_number,str) or len(draft.tracking_number.strip())>200:
        invalid('La guía / tracking debe tener hasta 200 caracteres.')
    if not isinstance(draft.supplier_alias,str) or len(draft.supplier_alias.strip())>100:
        invalid('El alias del proveedor debe tener hasta 100 caracteres.')
    if not draft.supplier.strip():
        invalid('Escribe el proveedor de la compra.')
    if type(draft.purchased_on) is not date or draft.purchased_on > date.today():
        invalid('La fecha de compra no puede ser futura.')
    if not draft.lines:
        invalid('Agrega al menos un producto físico.')
    if type(draft.costs_complete) is not bool:
        invalid('Revisa el estado de los costos.')
    for item in (*draft.lines, *draft.costs):
        if item.currency not in ('COP', 'USD'):
            invalid('Selecciona COP o USD.')
        required = item.currency == 'USD' or item.exchange_rate is not None or item.converted_on is not None
        if required:
            validate_rate(item.exchange_rate)
            if (type(item.converted_on) is not date or
                    not draft.purchased_on <= item.converted_on <= date.today()):
                invalid('Indica la fecha de conversión o referencia, entre la compra y hoy.')
    for line in draft.lines:
        if type(line.product_id) is not int or line.product_id <= 0:
            invalid('Selecciona un producto del catálogo.')
        if type(line.quantity) is not int or not 1 <= line.quantity <= MAX_CENTS:
            invalid('La cantidad debe ser un entero positivo.')
        check_cents(line.unit_cost_cents)
        check_cents(line_original_total(line))
    for cost in draft.costs:
        check_cents(cost.amount_cents)
        if cost.category not in categories:
            invalid('Selecciona una categoría de costo.')
        if cost.category == 'other' and categories.get('other') == CATEGORIES['other'] and not cost.description.strip():
            invalid('Describe el concepto de otros costos.')

    from .purchase_allocation import ALLOCATION_FIELDS, allocation_summary
    for line in draft.lines:
        for key,field in ALLOCATION_FIELDS.items():
            check_cents(getattr(line, field))
            if key not in categories and getattr(line,field):invalid('El gasto asignado no corresponde a un concepto de este pedido.')
        for key,value in line.extra_allocations.items():
            if key in ALLOCATION_FIELDS or key not in categories:invalid('Revisa los conceptos de los gastos asignados.')
            check_cents(value)
    if any(value < 0 for value in allocation_summary(draft)['remaining'].values()):
        invalid('Los gastos asignados superan los registrados en alguna categoría.')
    if draft.cost_states is not None:
        if (set(draft.cost_states) != set(categories) or
                any(v not in ('pending','recorded','not_applicable') for v in draft.cost_states.values())):
            invalid('Revisa el seguimiento de los conceptos.')
        for key, state in draft.cost_states.items():
            exists = any(c.category == key for c in draft.costs)
            if state == 'recorded' and not exists:
                invalid('Agrega el cargo de '+categories[key]+' antes de marcarlo registrado.')
            if state == 'not_applicable' and exists:
                invalid(categories[key]+': tiene cargos; no puede marcarse No aplica.')
        if draft.costs_complete != all(v != 'pending' for v in draft.cost_states.values()):
            invalid('El estado global no coincide con los conceptos pendientes.')


def calculate_purchase_totals(draft):
    validate_purchase(draft)
    return preview_purchase_totals(draft)


def preview_purchase_totals(draft):
    """Importes del borrador, independientes de cabecera y seguimiento pendientes."""
    categories=categories_for(draft)
    check_duplicate_vat(draft)
    for line in draft.lines:
        if type(line.quantity) is not int or not 1 <= line.quantity <= MAX_CENTS:
            invalid('La cantidad debe ser un entero positivo.')
        check_cents(line.unit_cost_cents)
    merchandise = sum(convert_to_cop(line_original_total(line), line.currency, line.exchange_rate)
                      for line in draft.lines)
    vat=sum(line_vat_cop(line) for line in draft.lines)
    shipping=0;taxes=vat
    for cost in draft.costs:
        if cost.category not in categories:
            invalid('Selecciona una categoría de costo.')
        value = convert_to_cop(cost.amount_cents, cost.currency, cost.exchange_rate)
        if definitions_for(draft)[cost.category]['group']=='shipping':
            shipping += value
        else:
            taxes += value
    total = merchandise + shipping + taxes
    check_cents(total)
    return PurchaseTotals(merchandise, shipping, taxes, total,vat)
