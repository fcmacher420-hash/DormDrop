from helpers import approved_listing


def setup_listing(client, make_user):
    seller_id, seller_headers = make_user("seller@campus.edu", is_seller=True)
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    buyer_id, buyer_headers = make_user("buyer@campus.edu")
    listing_id = approved_listing(client, seller_headers, admin_headers)
    return seller_id, seller_headers, buyer_id, buyer_headers, listing_id


def test_seller_can_reply_without_listing_context_and_sees_inbox(client, make_user):
    seller_id, seller_headers, buyer_id, buyer_headers, listing_id = setup_listing(client, make_user)
    assert client.post("/messages", json={"receiver_id": seller_id, "listing_id": listing_id, "body": "Available?"}, headers=buyer_headers).status_code == 201
    reply = client.post("/messages", json={"receiver_id": buyer_id, "body": "Yes, come by Hall A"}, headers=seller_headers)
    assert reply.status_code == 201

    inbox = client.get("/messages", headers=seller_headers).json()
    assert [c["peer_id"] for c in inbox] == [buyer_id]
    assert "campus.edu" not in str(inbox)
    thread = client.get(f"/messages/{buyer_id}", headers=seller_headers).json()
    assert [m["body"] for m in thread] == ["Available?", "Yes, come by Hall A"]


def test_first_contextual_chat_opens_empty_instead_of_erroring(client, make_user):
    seller_id, _, _, buyer_headers, listing_id = setup_listing(client, make_user)
    response = client.get(f"/messages/{seller_id}", params={"listing_id": listing_id}, headers=buyer_headers)
    assert response.status_code == 200 and response.json() == []


def test_strangers_cannot_chat(client, make_user):
    seller_id, _, buyer_id, _, listing_id = setup_listing(client, make_user)
    _, stranger_headers = make_user("stranger@campus.edu")
    assert client.post("/messages", json={"receiver_id": seller_id, "body": "hello"}, headers=stranger_headers).status_code == 403
    assert client.post("/messages", json={"receiver_id": buyer_id, "listing_id": listing_id, "body": "hello"}, headers=stranger_headers).status_code == 403
    assert client.get(f"/messages/{seller_id}", headers=stranger_headers).status_code == 403


def test_admin_chat_is_limited_to_sellers(client, make_user):
    admin_id, _ = make_user("boss@campus.edu", is_admin=True)
    _, seller_headers = make_user("seller2@campus.edu", is_seller=True)
    _, buyer_headers = make_user("buyer2@campus.edu")
    assert client.post("/messages", json={"receiver_id": admin_id, "body": "Need help"}, headers=seller_headers).status_code == 201
    assert client.post("/messages", json={"receiver_id": admin_id, "body": "Need help"}, headers=buyer_headers).status_code == 403
