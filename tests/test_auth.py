SIGNUP = {"email": "student@gmail.com", "password": "correct-horse", "campus": "UNZA", "dorm": "Hall A"}


def test_signup_verify_and_login(client):
    created = client.post("/auth/signup", json=SIGNUP)
    assert created.status_code == 201, created.text
    login = {"email": SIGNUP["email"], "password": SIGNUP["password"]}
    assert client.post("/auth/login", json=login).status_code == 403  # not verified yet
    assert client.post("/auth/verify", json={"token": created.json()["verification_token"]}).status_code == 200
    response = client.post("/auth/login", json=login)
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).json()["email"] == SIGNUP["email"]


def test_wrong_password_and_duplicate_email(client):
    assert client.post("/auth/signup", json=SIGNUP).status_code == 201
    assert client.post("/auth/signup", json=SIGNUP).status_code == 409
    assert client.post("/auth/login", json={"email": SIGNUP["email"], "password": "wrong-password"}).status_code == 401


def test_signup_rejects_non_gmail_email_and_overlong_password(client):
    assert client.post("/auth/signup", json={**SIGNUP, "email": "student@campus.edu"}).status_code == 422
    assert client.post("/auth/signup", json={**SIGNUP, "password": "a" * 73}).status_code == 422


def test_verification_accepts_token_with_surrounding_whitespace(client):
    created = client.post("/auth/signup", json=SIGNUP)
    assert created.status_code == 201
    token = created.json()["verification_token"]
    verified = client.post("/auth/verify", json={"token": f"  {token}\n"})
    assert verified.status_code == 200


def test_invalid_verification_token_can_be_refreshed_and_retried(client):
    created = client.post("/auth/signup", json=SIGNUP)
    assert created.status_code == 201
    original_token = created.json()["verification_token"]

    refreshed = client.post("/auth/verification-token", json={
        "email": SIGNUP["email"], "password": SIGNUP["password"]
    })
    assert refreshed.status_code == 200
    fresh_token = refreshed.json()["verification_token"]
    assert fresh_token != original_token
    assert client.post("/auth/verify", json={"token": original_token}).status_code == 400
    assert client.post("/auth/verify", json={"token": fresh_token}).status_code == 200
    assert client.post("/auth/login", json={
        "email": SIGNUP["email"], "password": SIGNUP["password"]
    }).status_code == 200


def test_verified_account_cannot_refresh_verification_token(client):
    created = client.post("/auth/signup", json=SIGNUP)
    assert created.status_code == 201
    token = created.json()["verification_token"]
    assert client.post("/auth/verify", json={"token": token}).status_code == 200
    refreshed = client.post("/auth/verification-token", json={
        "email": SIGNUP["email"], "password": SIGNUP["password"]
    })
    assert refreshed.status_code == 409


def test_foreign_seller_signup_is_separate_from_buyer_permissions(client):
    seller_payload = {"email": "supplier@example.jp", "password": "supplier-pass-1",
                      "account_type": "seller", "country": "Japan", "business_name": "Tokyo Campus Supply",
                      "contact_person": "Aiko Tanaka", "phone": "+81 90 1234 5678",
                      "business_description": "Wholesale supplies for student residences.",
                      "product_types": "Stationery, dorm essentials"}
    created = client.post("/auth/signup", json=seller_payload)
    assert created.status_code == 201
    assert client.post("/auth/verify", json={"token": created.json()["verification_token"]}).status_code == 200
    seller_login = client.post("/auth/login", json={"email": seller_payload["email"], "password": seller_payload["password"]})
    assert seller_login.status_code == 200
    seller_headers = {"Authorization": f"Bearer {seller_login.json()['access_token']}"}
    assert seller_login.json()["user"]["account_type"] == "seller"
    assert client.get("/cart", headers=seller_headers).status_code == 403
    assert client.post("/seller-requests", headers=seller_headers).status_code == 201
    assert client.get("/auth/me", headers=seller_headers).json()["contact_person"] == "Aiko Tanaka"
    partners = client.get("/partners").json()
    assert len(partners) == 1
    assert partners[0]["business_name"] == "Tokyo Campus Supply"
    assert partners[0]["phone"] == "+81 90 1234 5678"
    assert partners[0]["status"] == "Registered supplier"

    buyer_created = client.post("/auth/signup", json=SIGNUP)
    assert buyer_created.status_code == 201
    assert client.post("/auth/verify", json={"token": buyer_created.json()["verification_token"]}).status_code == 200
    buyer_login = client.post("/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]})
    buyer_headers = {"Authorization": f"Bearer {buyer_login.json()['access_token']}"}
    assert buyer_login.json()["user"]["account_type"] == "buyer"
    assert client.post("/seller-requests", headers=buyer_headers).status_code == 403
    assert client.get("/cart", headers=buyer_headers).status_code == 200


def test_partner_directory_excludes_buyers_and_marks_approved_sellers(client, make_user):
    _, seller_headers = make_user("pending@company.cn", account_type="seller", business_name="Beijing Supply",
                                  country="China", contact_person="Lin Wei", phone="+86 10 1234 5678",
                                  business_description="Supplies for student life.", product_types="Stationery")
    _, approved_headers = make_user("approved@company.jp", is_seller=True, business_name="Osaka Campus Goods",
                                    country="Japan", contact_person="Yuki Sato", phone="+81 6 1234 5678",
                                    business_description="Campus essentials and home goods.", product_types="Dorm essentials")
    make_user("buyer@campus.edu")
    partners = client.get("/partners").json()
    assert {partner["business_name"] for partner in partners} == {"Beijing Supply", "Osaka Campus Goods"}
    approved = next(partner for partner in partners if partner["business_name"] == "Osaka Campus Goods")
    assert approved["status"] == "Approved partner"


def test_signup_requires_profile_for_selected_role(client):
    assert client.post("/auth/signup", json={"email": "new@campus.edu", "password": "correct-horse",
                                             "account_type": "buyer"}).status_code == 422
    assert client.post("/auth/signup", json={"email": "supplier@example.cn", "password": "correct-horse",
                                             "account_type": "seller", "country": "China", "business_name": "Shenzhen Supply"}).status_code == 422


def test_protected_routes_require_a_token_and_reject_suspended_users(client, make_user):
    assert client.get("/cart").status_code == 401
    user_id, headers = make_user("buyer@campus.edu")
    _, admin_headers = make_user("admin@campus.edu", is_admin=True)
    assert client.get("/cart", headers=headers).status_code == 200
    assert client.post(f"/admin/users/{user_id}/suspend", headers=admin_headers).status_code == 200
    assert client.get("/cart", headers=headers).status_code == 401
    assert client.get("/admin/users", headers=headers).status_code in (401, 403)
