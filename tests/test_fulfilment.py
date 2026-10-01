from helpers import advance_to_delivered, approved_listing, buy, listing_payload


def test_declined_payment_changes_nothing(client, make_user):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    listing_id = approved_listing(client, seller_headers, admin_headers, quantity=3)
    client.post("/cart/items", json={"listing_id": listing_id, "quantity": 2}, headers=buyer_headers)

    declined = client.post("/checkout", json={"payment_method": "visa", "payment_details": "decline"}, headers=buyer_headers)
    assert declined.status_code == 400
    assert len(client.get("/cart", headers=buyer_headers).json()["items"]) == 1
    assert client.get("/listings").json()[0]["quantity"] == 3
    assert client.get("/orders", headers=buyer_headers).json() == []


def test_cannot_buy_more_than_stock_or_own_listing(client, make_user):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    listing_id = approved_listing(client, seller_headers, admin_headers, quantity=2)
    assert client.post("/cart/items", json={"listing_id": listing_id, "quantity": 3}, headers=buyer_headers).status_code == 409
    assert client.post("/cart/items", json={"listing_id": listing_id, "quantity": 1}, headers=seller_headers).status_code == 403


def test_money_is_exact_to_the_cent(client, make_user):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    listing_id = approved_listing(client, seller_headers, admin_headers, price=19.99, length_cm=10, width_cm=10,
                                  height_cm=10, weight_kg=1, quantity=5)
    client.post("/cart/items", json={"listing_id": listing_id, "quantity": 3}, headers=buyer_headers)
    cart = client.get("/cart", headers=buyer_headers).json()
    assert cart["subtotal"] == 59.97 and cart["shipping_fee"] == 9 and cart["grand_total"] == 68.97


def test_status_must_follow_the_sequence(client, make_user):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    order_id = buy(client, buyer_headers, approved_listing(client, seller_headers, admin_headers))
    skip = client.put(f"/admin/orders/{order_id}/status", json={"status": "delivered"}, headers=seller_headers)
    assert skip.status_code == 409
    assert client.put(f"/admin/orders/{order_id}/status", json={"status": "delivered"}, headers=buyer_headers).status_code == 403


def test_only_admin_can_advance_orders_with_several_sellers(client, make_user):
    _, first_headers = make_user("seller1@campus.edu", is_seller=True)
    _, second_headers = make_user("seller2@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    first = approved_listing(client, first_headers, admin_headers, title="Lamp")
    second = approved_listing(client, second_headers, admin_headers, title="Kettle")
    client.post("/cart/items", json={"listing_id": first, "quantity": 1}, headers=buyer_headers)
    client.post("/cart/items", json={"listing_id": second, "quantity": 1}, headers=buyer_headers)
    order_id = client.post("/checkout", json={"payment_method": "visa", "payment_details": "4242424242424242"}, headers=buyer_headers).json()["order_id"]

    assert client.put(f"/admin/orders/{order_id}/status", json={"status": "picked_up"}, headers=first_headers).status_code == 403
    assert client.put(f"/admin/orders/{order_id}/status", json={"status": "picked_up"}, headers=admin_headers).status_code == 200
    dashboard = client.get("/seller/dashboard", headers=first_headers).json()
    assert dashboard["sales"][0]["can_advance"] is False


def test_sellers_do_not_see_payment_details_of_orders(client, make_user):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    order_id = buy(client, buyer_headers, approved_listing(client, seller_headers, admin_headers))
    assert "payment_ref" in client.get(f"/orders/{order_id}", headers=buyer_headers).json()
    assert "payment_ref" not in client.get(f"/orders/{order_id}", headers=seller_headers).json()


def test_review_is_listed_once_per_seller_per_order(client, make_user):
    seller_id, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    order_id = buy(client, buyer_headers, approved_listing(client, seller_headers, admin_headers))
    assert client.post("/reviews", json={"order_id": order_id, "rating": 5}, headers=buyer_headers).status_code == 409  # not delivered yet
    advance_to_delivered(client, order_id, seller_headers)
    assert client.post("/reviews", json={"order_id": order_id, "rating": 5}, headers=buyer_headers).status_code == 201
    assert client.post("/reviews", json={"order_id": order_id, "rating": 1}, headers=buyer_headers).status_code == 409
    assert client.get("/orders", headers=buyer_headers).json()[0]["reviewed_seller_ids"] == [seller_id]


def test_payouts_are_limited_to_delivered_earnings_after_commission(client, make_user):
    seller_id, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    listing_id = approved_listing(client, seller_headers, admin_headers, price=120, quantity=3)
    order_id = buy(client, buyer_headers, listing_id, quantity=2)  # gross 240.00, 10% commission -> 216.00 net

    def payout(amount):
        return client.post("/admin/payouts", json={"seller_id": seller_id, "amount": amount, "reference": "MM-001"}, headers=admin_headers)

    assert payout(10).status_code == 409  # nothing delivered yet
    advance_to_delivered(client, order_id, seller_headers)
    dashboard = client.get("/seller/dashboard", headers=seller_headers).json()
    assert dashboard["gross_sales"] == 240 and dashboard["revenue_after_commission"] == 216 and dashboard["available_for_payout"] == 216
    assert payout(216.01).status_code == 409
    assert payout(100).status_code == 201
    assert payout(116.01).status_code == 409
    assert payout(116).status_code == 201
    final = client.get("/seller/dashboard", headers=seller_headers).json()
    assert final["paid_out"] == 216 and final["available_for_payout"] == 0
