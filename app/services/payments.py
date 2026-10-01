from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import uuid4


class PaymentProvider(ABC):
    @abstractmethod
    def charge(self, amount: Decimal, details: str) -> str:
        """Charge an amount and return a payment reference."""


class MobileMoneyProvider(PaymentProvider, ABC):
    """Adapter boundary for MTN, Airtel, or another mobile-money provider."""


def _is_decline(details: str) -> bool:
    return details.strip().lower() in {"fail", "decline", "declined"}


class MockProvider(MobileMoneyProvider):
    """Mock mobile-money provider used for development and tests."""
    method = "mobile_money"

    def charge(self, amount: Decimal, details: str) -> str:
        if _is_decline(details):
            raise ValueError("The mock payment was declined")
        return f"{self.method.upper()}-MOCK-{uuid4().hex[:12]}"


class MockVisaProvider(PaymentProvider):
    """Mock Visa processor; a gateway can implement PaymentProvider later."""
    method = "visa"

    def charge(self, amount: Decimal, details: str) -> str:
        if _is_decline(details):
            raise ValueError("The mock payment was declined")
        return f"{self.method.upper()}-MOCK-{uuid4().hex[:12]}"


def provider_for(method: str) -> PaymentProvider:
    """Payment adapters are replaceable; Visa and Mobile Money are mocked here."""
    return MockVisaProvider() if method == "visa" else MockProvider()
