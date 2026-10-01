"""Shared request helpers for the API tests."""


def listing_payload(**overrides):
    payload = {"title": "Desk chair", "description": "Good condition", "category": "Furniture", "price": 120,
               "length_cm": 10, "width_cm": 20, "height_cm": 10, "weight_kg": 0.5, "quantity": 3, "images": []}
    payload.update(overrides)
    return payload


def approved_listing(client, seller_headers, admin_headers, **overrides):
    created = client.post("/listings", json=listing_payload(**overrides), headers=seller_headers)
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    assert client.post(f"/admin/listings/{listing_id}/approve", headers=admin_headers).status_code == 200
    return listing_id


def buy(client, buyer_headers, listing_id, quantity=1, details="+260970000000"):
    assert client.post("/cart/items", json={"listing_id": listing_id, "quantity": quantity}, headers=buyer_headers).status_code == 201
    response = client.post("/checkout", json={"payment_method": "mobile_money", "payment_details": details}, headers=buyer_headers)
    assert response.status_code == 201, response.text
    return response.json()["order_id"]


def advance_to_delivered(client, order_id, headers):
    for status in ("picked_up", "in_transit", "delivered"):
        response = client.put(f"/admin/orders/{order_id}/status", json={"status": status}, headers=headers)
        assert response.status_code == 200, response.text
