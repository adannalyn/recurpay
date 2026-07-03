import uuid
import re
from datetime import datetime, timedelta

class Customer:
    def __init__(self, name, email, customer_id=None, virtual_account=None):
        self.customer_id = customer_id or str(uuid.uuid4())
        self.name = name
        self.email = email
        self.virtual_account = virtual_account or {}

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "virtual_account": self.virtual_account
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["email"], data["customer_id"], data.get("virtual_account"))

class Subscription:
    def __init__(self, customer_id, amount, frequency, start_date, description="", subscription_id=None, next_due_date=None, status="pending", last_payment_date=None, checkout_link=None):
        self.subscription_id = subscription_id or str(uuid.uuid4())
        self.customer_id = customer_id
        self.amount = amount
        self.frequency = frequency  # e.g., 'weekly', 'monthly', '90 days', 'custom:7'
        self.start_date = start_date  # datetime object
        self.description = description
        self.next_due_date = next_due_date or self._calculate_next_due_date()
        self.status = status  # 'pending', 'paid', 'overdue'
        self.last_payment_date = last_payment_date # datetime object
        self.checkout_link = checkout_link

    def _frequency_delta(self):
        frequency = self.frequency.strip().lower().replace("_", " ")
        named_frequencies = {
            "daily": 1,
            "day": 1,
            "weekly": 7,
            "week": 7,
            "biweekly": 14,
            "fortnightly": 14,
            "monthly": 30,
            "month": 30,
            "quarterly": 90,
            "quarter": 90,
            "yearly": 365,
            "annual": 365,
            "annually": 365,
            "year": 365,
        }

        if frequency in named_frequencies:
            return timedelta(days=named_frequencies[frequency])

        if frequency.startswith("custom:"):
            frequency = frequency.split(":", 1)[1].strip()

        match = re.fullmatch(r"(\d+)\s*(d|day|days)?", frequency)
        if match:
            return timedelta(days=int(match.group(1)))

        raise ValueError(
            "Frequency must be weekly, monthly, quarterly, yearly, custom:7, or a number of days like '90 days'."
        )

    def _calculate_next_due_date(self, anchor_date=None):
        anchor = anchor_date or self.start_date
        return anchor + self._frequency_delta()

    def update_next_due_date(self):
        anchor = self.next_due_date or self.last_payment_date or self.start_date
        self.next_due_date = self._calculate_next_due_date(anchor)

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
