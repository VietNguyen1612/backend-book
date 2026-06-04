import pytest
from unittest.mock import Mock, patch

class StripeAPI:
    def charge(self, amount: int, token: str) -> bool:
        # In real life, this makes an HTTP request
        pass

class PaymentService:
    def __init__(self, stripe_client: StripeAPI):
        self.stripe = stripe_client
        
    def process_order(self, order_id: str, amount: int, token: str):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        success = self.stripe.charge(amount, token)
        if success:
            return f"Order {order_id} processed"
        return f"Order {order_id} failed"

# TODO: Write tests using pytest
# - Test successful payment (Mock StripeAPI to return True)
# - Test failed payment (Mock StripeAPI to return False)
# - Test negative amount raises ValueError
