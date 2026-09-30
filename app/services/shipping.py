from app.core.config import settings

def chargeable_weight(length_cm: float, width_cm: float, height_cm: float, actual_weight_kg: float,
                      divisor: float | None = None) -> float:
    """Return the greater of actual and volumetric weight; volume is in cm³."""
    divisor = divisor or settings.volumetric_divisor
    if min(length_cm, width_cm, height_cm, actual_weight_kg, divisor) <= 0:
        raise ValueError("Dimensions, weight, and divisor must be positive")
    return max(actual_weight_kg, length_cm * width_cm * height_cm / divisor)

def shipping_fee(length_cm: float, width_cm: float, height_cm: float, actual_weight_kg: float) -> float:
    """Per-item fee in ZMW: base fee plus rate times chargeable kg."""
    weight = chargeable_weight(length_cm, width_cm, height_cm, actual_weight_kg)
    return round(settings.base_rate + settings.rate_per_kg * weight, 2)
