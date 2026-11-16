"""Tarifas por umbrales inclusivos, aplicadas al importe completo."""
from dataclasses import dataclass
from decimal import Decimal
import json
from .catalog import ValidationError


@dataclass(frozen=True)
class CommissionTier:
    from_cents: int
    rate_percent: Decimal
    fixed_cents: int = 0


def validate_fee(rate, fixed):
    from .sales import check_cents
    check_cents(fixed)
    if not isinstance(rate, Decimal) or not rate.is_finite() or not 0 <= rate <= 100 or rate.as_tuple().exponent < -6:
        raise ValidationError({'comision': 'Usa un porcentaje entre 0 y 100, con hasta 6 decimales.'})


def validate_tiers(tiers):
    from .sales import check_cents
    previous=0
    for tier in tiers:
        check_cents(tier.from_cents)
        if tier.from_cents <= previous:
            raise ValidationError({'comision': 'Los montos Desde deben ser positivos, únicos y estar en orden creciente.'})
        validate_fee(tier.rate_percent,tier.fixed_cents)
        previous=tier.from_cents


def effective_fee(method,total_cents):
    validate_fee(method.rate_percent,method.fixed_cents)
    validate_tiers(method.tiers)
    rate,fixed=method.rate_percent,method.fixed_cents
    for tier in method.tiers:
        if total_cents < tier.from_cents:break
        rate,fixed=tier.rate_percent,tier.fixed_cents
    return rate,fixed


def encode_tiers(tiers):
    validate_tiers(tiers)
    return json.dumps([[t.from_cents,str(t.rate_percent),t.fixed_cents] for t in tiers])


def decode_tiers(value):
    return tuple(CommissionTier(a,Decimal(b),c) for a,b,c in json.loads(value))
