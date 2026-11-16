"""Read-only FIFO valuation in integer-cent ranges, independent of stock writes."""
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Lot:
    key: object
    product_id: int
    quantity: int
    total_cents: int | None
    order: tuple
    purchase_id: int | None = None
    receipt_id: int | None = None
    reason: str = ''
    provisional: bool = False
    free: list = field(default_factory=list)

    def __post_init__(self):
        self.free = [(0, self.quantity)] if self.quantity else []

    def cost(self, start, quantity):
        if self.total_cents is None:
            return None
        return self.total_cents*(start+quantity)//self.quantity - self.total_cents*start//self.quantity


class FifoLedger:
    def __init__(self):
        self.lots = defaultdict(list)
        self.allocations = defaultdict(list)

    def add(self, lot):
        self.lots[lot.product_id].append(lot)
        self.lots[lot.product_id].sort(key=lambda item: item.order)

    def available(self, product_id):
        return sum(q for lot in self.lots[product_id] for _, q in lot.free)

    def consume(self, product_id, quantity, sale_id=None, receipt_id=None):
        taken = []
        for lot in self.lots[product_id]:
            if receipt_id is not None and lot.receipt_id != receipt_id:
                continue
            while quantity and lot.free:
                start, count = lot.free.pop(0)
                used = min(quantity, count)
                taken.append((lot, start, used))
                if used < count:
                    lot.free.insert(0, (start+used, count-used))
                quantity -= used
            if not quantity:
                break
        if quantity and receipt_id is None:
            # Historical inconsistency: preserve the quantity, never invent its price.
            lot = Lot(('missing', sale_id, product_id), product_id, quantity, None,
                      ('', 0), reason='Movimiento sin existencias trazables')
            lot.free = []
            taken.append((lot, 0, quantity))
            quantity = 0
        if sale_id is not None:
            self.allocations[sale_id, product_id].extend(taken)
        return quantity

    def restore(self, sale_id, product_id, quantity):
        tranches = self.allocations[sale_id, product_id]
        while quantity and tranches:
            lot, start, count = tranches.pop()
            used = min(quantity, count)
            if used < count:
                tranches.append((lot, start, count-used))
            if lot not in self.lots[product_id]:
                self.add(lot)
            lot.free.append((start+count-used, used))
            lot.free.sort()
            quantity -= used
        if quantity:
            self.add(Lot(('return', sale_id, product_id), product_id, quantity, None,
                         ('', 0), reason='Restitución sin costo trazable'))

    def reverse(self, receipt_id, product_id, quantity):
        for lot in self.lots[product_id]:
            if lot.receipt_id == receipt_id:
                lot.total_cents = None
                lot.reason = 'Recepción de origen revertida'
        remaining = self.consume(product_id, quantity, receipt_id=receipt_id)
        if remaining:
            self.consume(product_id, remaining)

    def value(self, sale_id, product_id):
        tranches = self.allocations[sale_id, product_id]
        known = sum(lot.cost(start, qty) or 0 for lot, start, qty in tranches)
        unknown = not tranches or any(lot.total_cents is None for lot, _, _ in tranches)
        return dict(cost_cents=None if unknown else known, known_cents=known,
                    quantity=sum(q for _, _, q in tranches),
                    provisional=any(lot.provisional for lot, _, _ in tranches),
                    reasons=sorted({lot.reason for lot, _, _ in tranches if lot.reason}),
                    purchases=sorted({lot.purchase_id for lot, _, _ in tranches if lot.purchase_id is not None}))
