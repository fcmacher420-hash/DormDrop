# DormDrop

DormDrop is a campus marketplace prototype built with FastAPI, SQLAlchemy, Alembic, MySQL, and plain HTML/CSS/JavaScript. Student buyer accounts use a university email and campus/residence profile. Seller accounts are a separate account type and can register with an international business email, country, and business name; an admin must approve a seller before they can list products. Each account has one role.

The home and browse pages show clickable product categories. A category opens its own page with approved listings filtered to that category. Available category names are Food, Clothing, Shoes, Electronics, Furniture, Personal Care, Stationery, Bags & Backpacks, Dorm Essentials, Cleaning & Laundry, Kitchenware, Sports & Fitness, and Books. Category image attributions are documented in [frontend/IMAGE-SOURCES.md](frontend/IMAGE-SOURCES.md).

## Run with Docker Compose

1. Copy `.env.example` to `.env`; replace the secret key, admin password, and both MySQL passwords. Keep `DATABASE_URL` in sync with `MYSQL_PASSWORD`.
   If you are upgrading from an earlier version, reset the old database first (`docker compose down -v`): the schema changed (exact money columns, new foreign-key rules) and the initial migration was rewritten.
2. Run `docker compose up --build`.
3. Open [http://localhost:8000](http://localhost:8000). Interactive API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

Compose waits for MySQL, applies Alembic migrations, seeds the admin and a sample listing, then starts the API and static frontend.

Seeded accounts (change passwords before use):

- Admin email and password come from `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`.
- Demo seller: `seller@demo.edu` / `SellerDemo123!` (created only while `SEED_DEMO_DATA=true`).

## Run locally without Docker

Use Python 3.11 or later. Create and activate a virtual environment, install requirements, set `DATABASE_URL` to a local MySQL instance (or `sqlite:///./dormdrop.db` for a quick local prototype), then run:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:DATABASE_URL = "sqlite:///./dormdrop.db"   # overrides the Docker-only host name in .env
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```


## Configuration

Extra settings (all optional, set in `.env`):

| Setting | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | With `production`, the app refuses to start on the default `SECRET_KEY`, the default admin password, a key shorter than 32 characters, or `SEED_DEMO_DATA=true`. |
| `ALLOWED_EMAIL_SUFFIXES` | `.edu` | Comma-separated email endings accepted at signup, e.g. `.edu,.ac.zm`. |
| `SEED_DEMO_DATA` | `true` | Creates the demo seller and sample listing. |

Money is stored as `NUMERIC(12,2)` and calculated with `Decimal`, rounded half-up to whole cents. Measurements are double precision.

Shipping is calculated for each unit and summed across the cart:

`chargeable_kg = max(actual_kg, length_cm × width_cm × height_cm ÷ 5000)`

`item_shipping_fee = base_rate + rate_per_kg × chargeable_kg`

Defaults are `BASE_RATE=2`, `RATE_PER_KG=1`, and `CURRENCY=ZMW`. The commission defaults to `COMMISSION_RATE=0.10` (10%). Rates and secrets are environment settings.

Both Visa and Mobile Money are mock providers in this prototype, as requested. Enter `decline` as payment details to simulate a declined payment. Email verification is also mocked: signup returns the token for local use. Never expose verification tokens in production.

## Tests

```powershell
python -m pytest
```

The suite covers shipping maths, order ID collisions, checkout side effects and rollback on a declined payment, signup/verify/login, listing input validation (including unsafe image URLs), privacy of public endpoints, chat access and seller replies, deleting listings that are in carts, order-status rules, payout limits, and that the Alembic migration matches the models.

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
| Chat | `GET /messages` (inbox), `GET /messages/{user_id}` (optional `listing_id`, `order_id`), `POST /messages` |
| Reviews | `POST /reviews`, `GET /sellers/{id}/reviews` |

All protected endpoints use `Authorization: Bearer <JWT>`. Public endpoints never return email addresses.

Order status rules: an admin can advance any order; a seller can advance an order only when every item in it is theirs. Payouts are limited to delivered orders, after commission (using the rate stored on each order), minus earlier payouts. Chat: a buyer and seller can message about a listing or order; once a thread exists either side can continue it; admins and sellers can message each other. Order states begin at `awaiting_pickup` and move in order through `picked_up`, `in_transit`, and `delivered`. A review can be submitted after delivery.

## Production notes

This is a runnable prototype. It stores JWTs in browser `localStorage` as requested; production should use secure, HttpOnly cookies, real email verification delivery, real Visa and mobile-money payment adapters, payment webhooks/idempotency, structured request/exception logging, and stronger operational configuration. Images are http(s) URL fields rather than uploads. Payment is charged before the order is committed; the mock providers make that safe, but a real adapter needs idempotency keys and refunds. Chat refresh is manual; realtime delivery is not included.
