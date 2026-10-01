import pytest
from helpers import approved_listing, buy, listing_payload

BAD_IMAGES = ['x" onerror="alert(1)', "javascript:alert(1)", "data:text/html;base64,PHNjcmlwdD4=", "ftp://example.com/a.png",
              "https://example.com/a b.png", "https://example.com/a'.png"]


@pytest.mark.parametrize("url", BAD_IMAGES)
def test_listing_rejects_unsafe_image_urls(client, make_user, url):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    response = client.post("/listings", json=listing_payload(images=[url]), headers=seller_headers)
    assert response.status_code == 422


def test_listing_accepts_https_image_and_rejects_bad_numbers(client, make_user):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    ok = client.post("/listings", json=listing_payload(images=["https://images.example.com/lamp.jpg?w=700"]), headers=seller_headers)
    assert ok.status_code == 201
    assert client.post("/listings", json=listing_payload(category="x" * 101), headers=seller_headers).status_code == 422
    assert client.post("/listings", json=listing_payload(price=10.123), headers=seller_headers).status_code == 422
    assert client.post("/listings", json=listing_payload(length_cm=5000), headers=seller_headers).status_code == 422


def test_public_endpoints_do_not_expose_emails(client, make_user):
    seller_id, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    buyer_id, buyer_headers = make_user("buyer@campus.edu")
    listing_id = approved_listing(client, seller_headers, admin_headers)
    order_id = buy(client, buyer_headers, listing_id)
    for status in ("picked_up", "in_transit", "delivered"):
        client.put(f"/admin/orders/{order_id}/status", json={"status": status}, headers=seller_headers)
    client.post("/reviews", json={"order_id": order_id, "rating": 4, "comment": "ok"}, headers=buyer_headers)

    detail = client.get(f"/listings/{listing_id}").json()
    assert "email" not in detail["seller"]
    assert "campus.edu" not in client.get(f"/listings/{listing_id}").text
    assert "campus.edu" not in client.get(f"/sellers/{seller_id}/reviews").text


def test_category_filter_is_case_insensitive(client, make_user):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    approved_listing(client, seller_headers, admin_headers, category="Furniture")
    assert len(client.get("/listings", params={"category": "furniture"}).json()) == 1
    assert client.get("/listings", params={"category": "books"}).json() == []


def test_deleting_a_listing_that_is_in_a_cart_or_chat_succeeds(client, make_user):
    seller_id, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    buyer_id, buyer_headers = make_user("buyer@campus.edu")
    listing_id = approved_listing(client, seller_headers, admin_headers)
    assert client.post("/cart/items", json={"listing_id": listing_id, "quantity": 1}, headers=buyer_headers).status_code == 201
    assert client.post("/messages", json={"receiver_id": seller_id, "listing_id": listing_id, "body": "Hi"}, headers=buyer_headers).status_code == 201

    assert client.delete(f"/listings/{listing_id}", headers=seller_headers).status_code == 204
    assert client.get("/cart", headers=buyer_headers).json()["items"] == []
    history = client.get(f"/messages/{seller_id}", headers=buyer_headers).json()
    assert [m["body"] for m in history] == ["Hi"] and history[0]["listing_id"] is None


def test_listing_that_was_ordered_cannot_be_deleted(client, make_user):
    _, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    _, buyer_headers = make_user("buyer@campus.edu")
    listing_id = approved_listing(client, seller_headers, admin_headers)
    buy(client, buyer_headers, listing_id)
    assert client.delete(f"/listings/{listing_id}", headers=seller_headers).status_code == 409
