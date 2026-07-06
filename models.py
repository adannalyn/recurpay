import uuid
import re
import calendar
from datetime import datetime, timedelta

class Customer:
    def __init__(self, name, email, customer_id=None, virtual_account=None, direct_debit_mandate=None):
        self.customer_id = customer_id or str(uuid.uuid4())
        self.name = name
        self.email = email
        self.virtual_account = virtual_account or {}
        self.direct_debit_mandate = direct_debit_mandate or {}

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "virtual_account": self.virtual_account,
            "direct_debit_mandate": self.direct_debit_mandate
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["name"],
            data["email"],
            data.get("customer_id"),
            data.get("virtual_account"),
            data.get("direct_debit_mandate")
        )

class Subscription:
    # Day-based frequencies: a fixed number of days, unaffected by month length.
    _DAY_FREQUENCIES = {
        "daily": 1,
        "day": 1,
        "weekly": 7,
        "week": 7,
        "biweekly": 14,
        "fortnightly": 14,
    }

    # Calendar-based frequencies: a fixed number of months, so due dates land
    # on the same day-of-month each cycle (clamped to the last valid day of
    # a shorter month, e.g. Jan 31 -> Feb 28).
    _MONTH_FREQUENCIES = {
        "monthly": 1,
        "month": 1,
        "quarterly": 3,
        "quarter": 3,
        "yearly": 12,
        "annual": 12,
        "annually": 12,
        "year": 12,
    }

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

    def _frequency_spec(self):
        """Parse self.frequency into ('days', n) or ('months', n)."""
        frequency = self.frequency.strip().lower().replace("_", " ")

        if frequency in self._DAY_FREQUENCIES:
            return ("days", self._DAY_FREQUENCIES[frequency])

        if frequency in self._MONTH_FREQUENCIES:
            return ("months", self._MONTH_FREQUENCIES[frequency])

        if frequency.startswith("custom:"):
            frequency = frequency.split(":", 1)[1].strip()

        match = re.fullmatch(r"(\d+)\s*(d|day|days)?", frequency)
        if match:
            return ("days", int(match.group(1)))

        raise ValueError(
            "Frequency must be weekly, monthly, quarterly, yearly, custom:7, or a number of days like '90 days'."
        )

    @staticmethod
    def _add_months(anchor, months):
        """Add a number of calendar months to a date, clamping the day to
        the last valid day of the resulting month (e.g. Jan 31 + 1 month
        -> Feb 28/29, not Mar 2 or 3)."""
        total_month_index = anchor.month - 1 + months
        year = anchor.year + total_month_index // 12
        month = total_month_index % 12 + 1
        last_day_of_month = calendar.monthrange(year, month)[1]
        day = min(anchor.day, last_day_of_month)
        return anchor.replace(year=year, month=month, day=day)

    def _calculate_next_due_date(self, anchor_date=None):
        anchor = anchor_date or self.start_date
        unit, amount = self._frequency_spec()
        if unit == "months":
            return self._add_months(anchor, amount)
        return anchor + timedelta(days=amount)

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
        next_due_date_raw = data.get("next_due_date")
        next_due_date = datetime.fromisoformat(next_due_date_raw) if next_due_date_raw else None
        last_payment_date_raw = data.get("last_payment_date")
        last_payment_date = datetime.fromisoformat(last_payment_date_raw) if last_payment_date_raw else None
        return cls(
            data["customer_id"],
            float(data["amount"]),
            data["frequency"],
            start_date,
            data.get("description", ""),
            data.get("subscription_id"),
            next_due_date,
            data.get("status", "pending"),
            last_payment_date,
            data.get("checkout_link")
        )