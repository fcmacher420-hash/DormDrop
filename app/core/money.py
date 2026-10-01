"""Decimal helpers so money is never handled as binary floating point."""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def as_decimal(value) -> Decimal:
    """Convert int/float/str/Decimal to Decimal without inheriting float noise (0.1 -> Decimal('0.1'))."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def to_money(value) -> Decimal:
    """Round to whole cents (ZMW ngwee) using half-up rounding."""
    return as_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
