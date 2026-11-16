from dataclasses import replace

import pytest

from mi_negocio.catalog import ProductInput, ValidationError, validate_product


def sample(**changes):
    return replace(ProductInput('010', 'Impresora 3D', 'product', '1234,56', True), **changes)


def test_preserves_code_and_exact_money():
    result = validate_product(sample())
    assert result.code == '010'
    assert result.price_cop_cents == 123456


@pytest.mark.parametrize('price,cents', [('0', 0), ('0.01', 1), ('12,50', 1250), ('92233720368547758.07', 9223372036854775807)])
def test_valid_prices(price, cents):
    assert validate_product(sample(price=price, kind='service')).price_cop_cents == cents


@pytest.mark.parametrize('price', ['-1', 'NaN', 'Infinity', '1,001', '1.001', '', '1e3', '1.000,00', '92233720368547758.08', '9' * 100])
def test_rejects_invalid_prices(price):
    with pytest.raises(ValidationError) as error:
        validate_product(sample(price=price))
    assert 'price' in error.value.errors


@pytest.mark.parametrize('field,value', [('code', ''), ('code', ' 010'), ('code', '010 '), ('name', '  '), ('kind', 'other')])
def test_rejects_invalid_fields(field, value):
    with pytest.raises(ValidationError) as error:
        validate_product(sample(**{field: value}))
    assert field in error.value.errors
