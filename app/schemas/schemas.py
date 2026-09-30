from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    campus: str = Field(min_length=2, max_length=150)
    dorm: str = Field(min_length=1, max_length=150)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class VerifyIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)

class ListingIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str
    category: str
    price: float = Field(gt=0)
    length_cm: float = Field(gt=0)
    width_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    weight_kg: float = Field(gt=0)
    quantity: int = Field(ge=1)
    images: list[str] = Field(default_factory=list)

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
    amount: float = Field(gt=0)
    reference: str = Field(min_length=2, max_length=120)
