from mi_negocio.fifo import FifoLedger, Lot


def test_fifo_cents_and_last_consumed_return():
    ledger = FifoLedger()
    ledger.add(Lot('a', 1, 3, 100, ('2026-01-01', 1)))
    ledger.add(Lot('b', 1, 2, 200, ('2026-01-02', 2)))
    ledger.consume(1, 4, sale_id=10)
    assert ledger.value(10, 1)['cost_cents'] == 200
    ledger.restore(10, 1, 2)
    assert ledger.value(10, 1)['cost_cents'] == 66
    ledger.consume(1, 3, sale_id=11)
    assert ledger.value(11, 1)['cost_cents'] == 234
    assert ledger.available(1) == 0


def test_unknown_lots_and_negative_adjustment():
    ledger = FifoLedger()
    ledger.add(Lot('physical', 1, 4, None, ('2026-01-01', 1), reason='Apertura física'))
    ledger.consume(1, 2)
    ledger.consume(1, 2, sale_id=10)
    assert ledger.value(10, 1)['cost_cents'] is None
    assert 'Apertura física' in ledger.value(10, 1)['reasons']


def test_large_quantities_use_ranges_and_preserve_rounding():
    ledger = FifoLedger()
    ledger.add(Lot('a', 1, 999999999, 123456789, ('2026-01-01', 1)))
    ledger.consume(1, 999999998, sale_id=10)
    ledger.consume(1, 1, sale_id=11)
    assert ledger.value(10, 1)['cost_cents'] + ledger.value(11, 1)['cost_cents'] == 123456789
    assert len(ledger.allocations[10, 1]) == 1
