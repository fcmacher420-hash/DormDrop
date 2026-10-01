from decimal import Decimal

from app.core.config import settings
from app.core.money import as_decimal, to_money


def chargeable_weight(length_cm: float, width_cm: float, height_cm: float, actual_weight_kg: float,
                      divisor: float | None = None) -> Decimal:
    """Return the greater of actual and volumetric weight (kg); volume is in cm³."""
    divisor = divisor or settings.volumetric_divisor
    if min(length_cm, width_cm, height_cm, actual_weight_kg, divisor) <= 0:
        raise ValueError("Dimensions, weight, and divisor must be positive")
    volumetric = as_decimal(length_cm) * as_decimal(width_cm) * as_decimal(height_cm) / as_decimal(divisor)
    return max(as_decimal(actual_weight_kg), volumetric)


def shipping_fee(length_cm: float, width_cm: float, height_cm: float, actual_weight_kg: float) -> Decimal:
    """Per-item fee in ZMW: base fee plus rate times chargeable kg, rounded to cents."""
    weight = chargeable_weight(length_cm, width_cm, height_cm, actual_weight_kg)
    return to_money(as_decimal(settings.base_rate) + as_decimal(settings.rate_per_kg) * weight)
