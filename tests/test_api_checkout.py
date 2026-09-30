from app.core.security import create_access_token
from app.models import User

def test_buyer_seller_admin_listing_checkout_tracking_review_and_chat(client):
    db_override = __import__("app.core.database", fromlist=["get_db"]).get_db
    db_gen = client.app.dependency_overrides[db_override]()
    db = next(db_gen)
    buyer = User(email="buyer@campus.edu", password_hash="x", campus="Campus", dorm="Hall", is_verified=True)
    seller = User(email="seller@campus.edu", password_hash="x", campus="Campus", dorm="Hall", is_verified=True, is_seller=True)
    admin = User(email="admin@campus.edu", password_hash="x", campus="Campus", dorm="Admin", is_verified=True, is_admin=True)
    db.add_all([buyer, seller, admin]); db.commit()
    buyer_id, seller_id, admin_id = buyer.id, seller.id, admin.id
    db.close()
    buyer_headers = {"Authorization": f"Bearer {create_access_token(buyer_id)}"}
    seller_headers = {"Authorization": f"Bearer {create_access_token(seller_id)}"}
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

    listing_payload = {"title": "Desk chair", "description": "Good condition", "category": "Furniture",
                       "price": 120, "length_cm": 10, "width_cm": 20, "height_cm": 10,
                       "weight_kg": .5, "quantity": 3, "images": []}
    created = client.post("/listings", json=listing_payload, headers=seller_headers)
    assert created.status_code == 201
    listing_id = created.json()["id"]
    assert created.json()["status"] == "pending_approval"
    assert client.get("/listings").json() == []
    assert client.post(f"/admin/listings/{listing_id}/approve", headers=admin_headers).status_code == 200
    assert len(client.get("/listings").json()) == 1

    assert client.post("/cart/items", json={"listing_id": listing_id, "quantity": 2}, headers=buyer_headers).status_code == 201
    cart = client.get("/cart", headers=buyer_headers).json()
    assert cart["subtotal"] == 240 and cart["shipping_fee"] == 5 and cart["grand_total"] == 245
    order = client.post("/checkout", json={"payment_method": "mobile_money", "payment_details": "+260970000000"}, headers=buyer_headers)
    assert order.status_code == 201
    assert order.json()["status"] == "awaiting_pickup"
    order_id = order.json()["order_id"]
    for status in ("picked_up", "in_transit", "delivered"):
        response = client.put(f"/admin/orders/{order_id}/status", json={"status": status}, headers=seller_headers)
        assert response.status_code == 200

    review = client.post("/reviews", json={"order_id": order_id, "seller_id": seller_id, "rating": 5, "comment": "Great find"}, headers=buyer_headers)
    assert review.status_code == 201
    assert client.get(f"/sellers/{seller_id}/reviews").json()[0]["rating"] == 5
    message = client.post("/messages", json={"receiver_id": seller_id, "listing_id": listing_id, "body": "Thanks!"}, headers=buyer_headers)
    assert message.status_code == 201
    assert client.post("/messages", json={"receiver_id": admin_id, "body": "Need help"}, headers=seller_headers).status_code == 201
