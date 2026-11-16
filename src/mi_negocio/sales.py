"""Tipos y cálculos monetarios independientes de la interfaz."""
from dataclasses import dataclass
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from .catalog import ValidationError

MAX_CENTS = 2**63 - 1


def money(value: str) -> int:
    try:
        text = value.strip()
        if re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?', text):
            text = text.replace('.', '')
        number = Decimal(text.replace(',', '.'))
        if not number.is_finite() or number < 0 or number > Decimal(MAX_CENTS)/100 or number.as_tuple().exponent < -2:
            raise ValueError
        return int(number * 100)
    except (ValueError, ArithmeticError):
        raise ValidationError({'importe': 'Usa un importe como 42500,50 o 42.500,50, con hasta dos decimales.'})


def check_cents(value):
    if type(value) is not int or not 0 <= value <= MAX_CENTS:
        raise ValidationError({'importe': 'El importe no es válido o excede el límite permitido.'})


@dataclass(frozen=True)
class SaleLineInput:
    product_id: int
    quantity: int
    unit_price_cents: int


@dataclass(frozen=True)
class SaleDraft:
    sold_on: date
    invoice_ref: str
    lines: tuple[SaleLineInput, ...]
    method_id: int
    destination_account_id: int
    shipping_enabled: bool = False
    shipping_charged_cents: int = 0
    shipping_cost_cents: int = 0
    customer_name: str = ""
    carrier_id: int | None = None
    destination_city: str = ""
    has_withholding: bool = False
    tracking_number: str = ""
    customer_identification: str = ""
    customer_email: str = ""
    commission_override: tuple[Decimal, int] | None = None
    vat_enabled: bool = False
    vat_rate: Decimal = Decimal('19')
    vat_included: bool = False
    customer_alias: str = ''
    customer_phone: str = ''


@dataclass(frozen=True)
class ReceiptInput:
    received_on: date
    account_id: int
    commission_cents: int


@dataclass(frozen=True)
class ShippingPaymentInput:
    paid_on: date
    account_id: int | None
    payment_kind: str = "unspecified"


@dataclass(frozen=True)
class Totals:
    subtotal_cents: int
    total_cents: int
    commission_cents: int
    deposit_cents: int
    net_after_shipping_cents: int
    base_cents: int = 0
    vat_cents: int = 0


@dataclass(frozen=True)
class PaymentMethod:
    id: int
    name: str
    provider: str
    rate_percent: Decimal
    fixed_cents: int
    enabled: bool = True
    placement: str = 'primary'
    default_received: bool = True
    account_kind: str = 'any'
    tiers: tuple = ()


@dataclass(frozen=True)
class Account:
    id: int
    name: str
    enabled: bool = True
    kind: str = 'bank'
    is_default: bool = False


@dataclass(frozen=True)
class SalesFilter:
    start: date | None = None
    end: date | None = None
    account_id: int | None = None
    received: bool | None = None
    query: str = ''
    has_withholding: bool | None = None
    cancelled: bool | None = False
    vat_enabled: bool | None = None


def calculate_totals(lines, shipping_charged_cents, shipping_cost_cents, rate_percent, fixed_cents, *, vat_enabled=False, vat_rate=Decimal('19'), vat_included=False) -> Totals:
    if not lines:
        raise ValidationError({'productos': 'Agrega al menos un producto o servicio.'})
    for value in (shipping_charged_cents, shipping_cost_cents, fixed_cents):
        check_cents(value)
    if not isinstance(rate_percent, Decimal) or not rate_percent.is_finite() or not 0 <= rate_percent <= 100:
        raise ValidationError({'comision': 'El porcentaje debe estar entre 0 y 100.'})
    subtotal = 0
    for line in lines:
        check_cents(line.unit_price_cents)
        if type(line.quantity) is not int or not 1 <= line.quantity <= MAX_CENTS:
            raise ValidationError({'cantidad': 'La cantidad debe ser un entero positivo.'})
        subtotal += line.quantity * line.unit_price_cents
        check_cents(subtotal)
    from .vat import split_vat
    base,vat,subtotal=split_vat(subtotal,vat_enabled,vat_rate,vat_included)
    total = subtotal + shipping_charged_cents
    check_cents(total)
    commission = int((Decimal(total)*rate_percent/100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) + fixed_cents
    if commission > total:
        raise ValidationError({'comision': 'La comisión no puede superar el total de la venta.'})
    return Totals(subtotal,total,commission,total-commission,total-commission-shipping_cost_cents,base,vat)


def validate_sale(draft: SaleDraft):
    if not draft.customer_name.strip():
        raise ValidationError({"cliente": "Escribe el nombre del cliente."})
    if not isinstance(draft.sold_on, date) or draft.sold_on > date.today():
        raise ValidationError({'fecha': 'La fecha de venta no puede ser futura.'})
    if not draft.method_id or not draft.destination_account_id:
        raise ValidationError({'pago': 'Selecciona forma de pago y cuenta de destino.'})
    if not draft.shipping_enabled and (draft.shipping_charged_cents or draft.shipping_cost_cents):
        raise ValidationError({'envio': 'Activa el envío para registrar sus importes.'})


def informative_withholding(total_cents: int) -> int:
    """Estimación solicitada: 2,5 % del total comercial, incluido envío cobrado."""
    check_cents(total_cents)
    return int((Decimal(total_cents) * Decimal('0.025')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


SHIPPING_PAYMENT_KINDS = {"unspecified": "Por completar", "account": "Desde una cuenta", "debit_card": "Tarjeta débito", "credit_card": "Tarjeta crédito"}
