import re
from decimal import Decimal

from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# http(s) only, no whitespace or characters that could break out of an HTML attribute.
_IMAGE_URL = re.compile(r"^https?://[^\s\"'<>`]+$", re.IGNORECASE)
MAX_IMAGES = 10


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    account_type: Literal["buyer", "seller"] = "buyer"
    campus: str | None = Field(default=None, min_length=2, max_length=150)
    dorm: str | None = Field(default=None, min_length=1, max_length=150)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    business_name: str | None = Field(default=None, min_length=2, max_length=150)
    contact_person: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, min_length=7, max_length=40)
    business_description: str | None = Field(default=None, min_length=10, max_length=3000)
    product_types: str | None = Field(default=None, min_length=2, max_length=500)

    @model_validator(mode="after")
    def validate_account_profile(self):
        if self.account_type == "buyer" and (not self.campus or not self.dorm):
            raise ValueError("Buyers must provide their campus and residence")
        seller_fields = (self.country, self.business_name, self.contact_person, self.phone,
                         self.business_description, self.product_types)
        if self.account_type == "seller" and any(not value for value in seller_fields):
            raise ValueError("Sellers must complete the business and contact registration details")
        return self

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        # bcrypt only uses the first 72 bytes; refuse longer input instead of silently truncating.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class VerifyIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class ListingIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    length_cm: float = Field(gt=0, le=1000)
    width_cm: float = Field(gt=0, le=1000)
    height_cm: float = Field(gt=0, le=1000)
    weight_kg: float = Field(gt=0, le=500)
    quantity: int = Field(ge=1, le=10000)
    images: list[str] = Field(default_factory=list, max_length=MAX_IMAGES)

    @field_validator("images")
    @classmethod
    def images_are_safe_urls(cls, urls: list[str]) -> list[str]:
        for url in urls:
            if len(url) > 1000 or not _IMAGE_URL.match(url):
                raise ValueError("Image URLs must be http(s) links of at most 1000 characters")
        return urls


class CartAddIn(BaseModel):
    listing_id: int
    quantity: int = Field(ge=1)


class CartUpdateIn(BaseModel):
    quantity: int = Field(ge=1)


class CheckoutIn(BaseModel):
    payment_method: str = Field(pattern="^(visa|mobile_money)$")
    payment_details: str = Field(min_length=4, max_length=64)


class ReviewIn(BaseModel):
    order_id: str
    seller_id: int | None = None
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class MessageIn(BaseModel):
    receiver_id: int
    body: str = Field(min_length=1, max_length=4000)
    listing_id: int | None = None
    order_id: str | None = None


class StatusIn(BaseModel):
    status: str = Field(pattern="^(picked_up|in_transit|delivered)$")


class PayoutIn(BaseModel):
    seller_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reference: str = Field(min_length=2, max_length=120)
