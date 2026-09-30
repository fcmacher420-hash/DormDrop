# DormDrop

DormDrop is a campus-only student marketplace prototype built with FastAPI, SQLAlchemy, Alembic, MySQL, and plain HTML/CSS/JavaScript.

## Run with Docker Compose

1. Copy `.env.example` to `.env`; replace the secret key, admin password, and both MySQL passwords. Keep `DATABASE_URL` in sync with `MYSQL_PASSWORD`.
2. Run `docker compose up --build`.
3. Open [http://localhost:8000](http://localhost:8000). Interactive API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

Compose waits for MySQL, applies Alembic migrations, seeds the admin and a sample listing, then starts the API and static frontend.

Seeded accounts (change passwords before use):

- Admin email and password come from `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`.
- Demo seller: `seller@demo.edu` / `SellerDemo123!`.

## Run locally without Docker

Use Python 3.11 or later. Create and activate a virtual environment, install requirements, set `DATABASE_URL` to a local MySQL instance (or `sqlite:///./dormdrop.db` for a quick local prototype), then run:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

## Configuration

Shipping is calculated for each unit and summed across the cart:

`chargeable_kg = max(actual_kg, length_cm × width_cm × height_cm ÷ 5000)`

`item_shipping_fee = base_rate + rate_per_kg × chargeable_kg`

Defaults are `BASE_RATE=2`, `RATE_PER_KG=1`, and `CURRENCY=ZMW`. The commission defaults to `COMMISSION_RATE=0.10` (10%). Rates and secrets are environment settings.

Both Visa and Mobile Money are mock providers in this prototype, as requested. Enter `decline` as payment details to simulate a declined payment. Email verification is also mocked: signup returns the token for local use. Never expose verification tokens in production.

## Tests

```powershell
pytest
```

The suite covers chargeable-weight selection and shipping, order ID collision checks, and checkout side effects (order, stock, cart, and commission).

## API overview

| Area | Routes |
|---|---|
| Authentication | `POST /auth/signup`, `/auth/login`, `/auth/verify`; `GET /auth/me` |
| Listings | `GET /listings`, `GET /listings/{id}`, `POST /listings`, `PUT/DELETE /listings/{id}`, `POST /listings/{id}/sold` |
| Listing moderation | `GET /admin/listings`, `GET /admin/listings/pending`, `POST /admin/listings/{id}/approve`, `/disapprove`, `PUT /admin/listings/{id}` |
| Cart and checkout | `GET /cart`, `POST /cart/items`, `PUT/DELETE /cart/items/{id}`, `POST /checkout` |
| Orders | `GET /orders`, `GET /orders/{order_id}`, `PUT /admin/orders/{order_id}/status`, `GET /admin/orders` |
| Seller onboarding | `POST /seller-requests`, `GET /admin/seller-requests`, `POST /admin/seller-requests/{id}/approve` or `/reject` |
| Seller dashboard | `GET /seller/dashboard`, `GET /seller/admin-contact` |
| Users | `GET /admin/users`, `POST /admin/users/{id}/suspend` or `/unsuspend` |
| Commissions and payouts | `GET /admin/commissions`, `POST /admin/payouts` |
| Chat | `GET /messages/{user_id}`, `POST /messages` |
| Reviews | `POST /reviews`, `GET /sellers/{id}/reviews` |

All protected endpoints use `Authorization: Bearer <JWT>`. Order states begin at `awaiting_pickup` and move in order through `picked_up`, `in_transit`, and `delivered`. A review can be submitted after delivery.

## Production notes

This is a runnable prototype. It stores JWTs in browser `localStorage` as requested; production should use secure, HttpOnly cookies, real email verification delivery, real Visa and mobile-money payment adapters, payment webhooks/idempotency, structured request/exception logging, and stronger operational configuration. Images are URL fields rather than uploads. Chat refresh is manual; realtime delivery is not included.
