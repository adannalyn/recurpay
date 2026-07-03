import uuid
from datetime import datetime, timedelta

class Customer:
    def __init__(self, name, email, customer_id=None):
        self.customer_id = customer_id or str(uuid.uuid4())
        self.name = name
        self.email = email

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email
        }

@classmethod
def from_dict(cls, data):
        return cls(data["name"], data["email"], data["customer_id"])

class Subscription:
    def __init__(self, customer_id, amount, frequency, start_date, description="", subscription_id=None, next_due_date=None, status="pending", last_payment_date=None, checkout_link=None):
        self.subscription_id = subscription_id or str(uuid.uuid4())
        self.customer_id = customer_id
        self.amount = amount
        self.frequency = frequency  # e.g., 'weekly', 'monthly', 'custom:7' (for 7 days)
        self.start_date = start_date  # datetime object
        self.description = description
        self.next_due_date = next_due_date or self._calculate_next_due_date()
        self.status = status  # 'pending', 'paid', 'overdue'
        self.last_payment_date = last_payment_date # datetime object
        self.checkout_link = checkout_link

    def _calculate_next_due_date(self):
        if self.frequency == 'weekly':
            return self.start_date + timedelta(weeks=1)
        elif self.frequency == 'monthly':
            # Simple monthly calculation, can be improved for exact day of month
            return self.start_date + timedelta(days=30) # Approximation
        elif self.frequency.startswith('custom:'):
            days = int(self.frequency.split(':')[1])
            return self.start_date + timedelta(days=days)
        return self.start_date # Default to start date if frequency is unknown

    def update_next_due_date(self):
        self.next_due_date = self._calculate_next_due_date()

    def to_dict(self):
        return {
            "subscription_id": self.subscription_id,
            "customer_id": self.customer_id,
            "amount": str(self.amount), # Store as string to avoid float precision issues
            "frequency": self.frequency,
            "start_date": self.start_date.isoformat(),
            "description": self.description,
            "next_due_date": self.next_due_date.isoformat(),
            "status": self.status,
            "last_payment_date": self.last_payment_date.isoformat() if self.last_payment_date else None,
            "checkout_link": self.checkout_link
        }

@classmethod
def from_dict(cls, data):
        start_date = datetime.fromisoformat(data["start_date"])
        next_due_date = datetime.fromisoformat(data["next_due_date"])
        last_payment_date = datetime.fromisoformat(data["last_payment_date"]) if data["last_payment_date"] else None
        return cls(
            data["customer_id"],
            float(data["amount"]),
            data["frequency"],
            start_date,
            data["description"],
            data["subscription_id"],
            next_due_date,
            data["status"],
            last_payment_date,
            data["checkout_link"]
        )
