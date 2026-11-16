import sqlite3

import pytest

from mi_negocio.catalog import ProductInput, validate_product
from mi_negocio.repository import CatalogRepository, DuplicateCodeError, StorageError


def item(code='010', name='Impresora', kind='product', active=True):
    return validate_product(ProductInput(code, name, kind, '1234,56', active))


@pytest.fixture
def repo(tmp_path):
    repository = CatalogRepository(tmp_path / 'catalog.sqlite3')
    yield repository
    repository.close()


def test_persists_after_reopening(tmp_path):
    path = tmp_path / 'una carpeta' / 'catalog.sqlite3'
    with_repo = CatalogRepository(path)
    product = with_repo.create(item())
    with_repo.close()
    reopened = CatalogRepository(path)
    try:
        assert reopened.list_products() == [product]
        assert product.code == '010'
        assert product.price_cop_cents == 123456
    finally:
        reopened.close()


def test_duplicate_does_not_insert_and_case_is_preserved(repo):
    repo.create(item('A'))
    with pytest.raises(DuplicateCodeError):
        repo.create(item('A'))
    repo.create(item('a'))
    assert {p.code for p in repo.list_products()} == {'A', 'a'}


def test_update_keeps_identity_and_duplicate_rolls_back(repo):
    original = repo.create(item())
    repo.create(item('002'))
    with pytest.raises(DuplicateCodeError):
        repo.update(original.id, item('002', 'Incorrecto'))
    assert repo.list_products(query='010')[0].name == 'Impresora'
    edited = repo.update(original.id, item('001', 'Nuevo nombre'))
    assert edited.id == original.id
    assert edited.created_at == original.created_at
    assert edited.name == 'Nuevo nombre'


def test_filters_and_literal_search(repo):
    product = repo.create(item('010', 'Impresión 3D'))
    repo.create(item('S_1', 'Servicio 100%', 'service'))
    repo.create(item('OLD', 'Otro', active=False))
    assert [p.id for p in repo.list_products('IMPRESIÓN', 'product', True)] == [product.id]
    assert [p.code for p in repo.list_products('%')] == ['S_1']
    assert [p.code for p in repo.list_products('_')] == ['S_1']
    assert [p.code for p in repo.list_products(active=False)] == ['OLD']


def test_deactivation_is_reversible(repo):
    product = repo.create(item())
    repo.set_active(product.id, False)
    assert repo.list_products(active=True) == []
    repo.set_active(product.id, True)
    restored = repo.list_products()[0]
    assert restored.id == product.id
    assert restored.price_cop_cents == 123456


def test_future_version_is_not_overwritten(tmp_path):
    path = tmp_path / 'future.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA user_version=99')
        connection.execute('CREATE TABLE sentinel (value TEXT)')
        connection.execute("INSERT INTO sentinel VALUES ('keep')")
    with pytest.raises(StorageError):
        CatalogRepository(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT value FROM sentinel').fetchone() == ('keep',)
        assert connection.execute('PRAGMA user_version').fetchone() == (99,)


def test_locked_write_is_reported_and_no_partial_row(repo, tmp_path):
    connection = sqlite3.connect(tmp_path / 'catalog.sqlite3')
    connection.execute('BEGIN EXCLUSIVE')
    try:
        with pytest.raises(StorageError):
            repo.create(item())
    finally:
        connection.rollback()
        connection.close()
    assert repo.list_products() == []


def test_invalid_database_path_is_reported(tmp_path):
    with pytest.raises(StorageError):
        CatalogRepository(tmp_path)


def test_missing_update_is_not_reported_as_success(repo):
    with pytest.raises(StorageError):
        repo.update(999, item())
    with pytest.raises(StorageError):
        repo.set_active(999, False)


def classified(code='010', brand='Bambu Lab', subtype='Impresora 3D'):
    return validate_product(ProductInput(code, 'Máquina', 'product', '1234,56', True, brand, subtype))


def test_classifications_reused_and_filtered(repo):
    repo.create(classified())
    repo.create(classified('011', ' bambu lab ', 'Láser de diodo'))
    assert repo.list_options('brand') == ['Bambu Lab']
    assert len(repo.list_products(brand='Bambu Lab')) == 2
    assert [p.code for p in repo.list_products(brand='Bambu Lab', subtype='Impresora 3D')] == ['010']
    assert repo.list_products()[0].price_cop_cents == 123456


def test_rename_updates_associated_products_and_rejects_duplicate(repo):
    repo.create(classified())
    repo.add_option('brand', 'Otro')
    repo.rename_option('brand', 'Bambu Lab', 'Bambu')
    assert repo.list_products()[0].brand == 'Bambu'
    with pytest.raises(StorageError):
        repo.rename_option('brand', 'Bambu', 'Otro')
    assert repo.list_products()[0].brand == 'Bambu'
    with pytest.raises(StorageError):
        repo.add_option('subtype', '  ')


def test_duplicate_product_rolls_back_new_options(repo):
    repo.create(classified())
    with pytest.raises(DuplicateCodeError):
        repo.create(classified(brand='No guardar', subtype='Tampoco'))
    assert repo.list_options('brand') == ['Bambu Lab']
    assert repo.list_options('subtype') == ['Impresora 3D']


def test_migration_preserves_v1_data(tmp_path):
    path = tmp_path / 'old.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE products (id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, kind TEXT, price_cop_cents INTEGER, active INTEGER, created_at TEXT, updated_at TEXT)')
        db.execute("INSERT INTO products VALUES (5,'010','Anterior','product',150025,1,'antes','antes')")
        db.execute('PRAGMA user_version=1')
    migrated = CatalogRepository(path)
    try:
        product = migrated.list_products()[0]
        assert (product.id, product.code, product.price_cop_cents, product.created_at) == (5, '010', 150025, 'antes')
        assert product.brand == product.subtype == ''
        migrated.update(5, classified())
    finally:
        migrated.close()
    reopened = CatalogRepository(path)
    assert reopened.list_products()[0].brand == 'Bambu Lab'
    reopened.close()
