import pytest
from app.services.shipping import chargeable_weight, shipping_fee

def test_uses_max_of_actual_and_volumetric_weight():
    assert chargeable_weight(50, 40, 30, 2) == 12
    assert chargeable_weight(10, 10, 10, 4) == 4

def test_shipping_fee_uses_per_item_configured_rates():
    # 50×40×30/5000 = 12 kg; configured fee is 2 + 1×12 ZMW.
    assert shipping_fee(50, 40, 30, 2) == 14

def test_shipping_rejects_non_positive_measurements():
    with pytest.raises(ValueError):
        chargeable_weight(0, 2, 3, 1)
