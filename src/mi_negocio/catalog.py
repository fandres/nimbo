"""Reglas del catálogo, independientes de Qt y SQLite."""

from dataclasses import dataclass, field
from decimal import Decimal
import re


@dataclass(frozen=True)
class ProductInput:
    code: str
    name: str
    kind: str
    price: str
    active: bool = True
    brand: str = ""
    subtype: str = ""


@dataclass(frozen=True)
class ValidatedProduct:
    code: str
    name: str
    kind: str
    price_cop_cents: int
    active: bool
    brand: str = field(default="", kw_only=True)
    subtype: str = field(default="", kw_only=True)


@dataclass(frozen=True)
class Product(ValidatedProduct):
    id: int
    created_at: str
    updated_at: str


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__('Revisa los campos indicados.')


def validate_product(data: ProductInput) -> ValidatedProduct:
    errors = {}
    if not data.code or not data.code.strip():
        errors['code'] = 'Ingresa el código de tu catálogo.'
    elif data.code != data.code.strip():
        errors['code'] = 'El código no debe tener espacios al inicio o al final.'
    if not data.name.strip():
        errors['name'] = 'Ingresa el nombre.'
    if data.kind not in ('product', 'service'):
        errors['kind'] = 'Selecciona Producto o Servicio.'
    price = data.price.strip()
    cents = 0
    if len(price) > 22 or not re.fullmatch(r'[0-9]+(?:[.,][0-9]{1,2})?', price):
        errors['price'] = 'Usa un valor positivo o cero, sin miles y con hasta dos decimales.'
    else:
        cents = int(Decimal(price.replace(',', '.')) * 100)
        if cents > 9223372036854775807:
            errors['price'] = 'El precio excede el máximo permitido.'
    if errors:
        raise ValidationError(errors)
    return ValidatedProduct(data.code, data.name.strip(), data.kind, cents, data.active, brand=data.brand.strip(), subtype=data.subtype.strip())
