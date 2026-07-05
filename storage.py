import json
import os
from datetime import datetime
from config import DATA_FILE
from models import Customer, Subscription

# IDs from data.example.json's template. A real customer always gets a
# randomly generated UUID, so these exact literal IDs can only ever be
# leftover seed data from the old auto-copy behavior - never a genuine
# customer who happens to share a name like "Jane Doe".
_PLACEHOLDER_CUSTOMER_IDS = {"example-customer-id-1", "example-customer-id-2"}
_PLACEHOLDER_SUBSCRIPTION_IDS = {"example-subscription-id-1"}

class JSONStorage:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.data = self._load_data()

    def _load_data(self):
        # First run: start with a genuinely empty data file. data.example.json
        # is kept purely as a reference template for the expected shape of
        # the data - it is never copied into data.json, since doing so used
        # to leave permanent placeholder customers (Jane Doe / John Doe) in
        # real data with no clear way to tell they weren't real records.
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w") as f:
                json.dump(
                    {"customers": [], "subscriptions": []},
                    f,
                    indent=4
                )

        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)

            data["customers"] = [
                Customer.from_dict(c)
                for c in data.get("customers", [])
            ]
            data["subscriptions"] = [
                Subscription.from_dict(s)
                for s in data.get("subscriptions", [])
            ]

            data = self._purge_placeholder_seed_data(data)

            return data


        except (json.JSONDecodeError, FileNotFoundError):
            return {
                "customers": [],
                "subscriptions": []
            }

    def _purge_placeholder_seed_data(self, data):
        """One-time cleanup: earlier versions of this app auto-copied
        data.example.json into data.json on first run, permanently mixing
        placeholder customers (Jane Doe / John Doe) into real data with no
        way to tell them apart from genuine records. This strips out any
        records still carrying those exact known placeholder IDs and saves
        the cleaned result immediately, so it only needs to run once per
        affected data.json - it's effectively a no-op after that."""
        placeholder_customers = [
            c for c in data["customers"] if c.customer_id in _PLACEHOLDER_CUSTOMER_IDS
        ]
        placeholder_subscriptions = [
            s for s in data["subscriptions"]
            if s.subscription_id in _PLACEHOLDER_SUBSCRIPTION_IDS
            or s.customer_id in _PLACEHOLDER_CUSTOMER_IDS
        ]

        if not placeholder_customers and not placeholder_subscriptions:
            return data

        removed_customer_ids = {c.customer_id for c in placeholder_customers}
        removed_subscription_ids = {s.subscription_id for s in placeholder_subscriptions}

        data["customers"] = [
            c for c in data["customers"] if c.customer_id not in removed_customer_ids
        ]
        data["subscriptions"] = [
            s for s in data["subscriptions"] if s.subscription_id not in removed_subscription_ids
        ]

        print(
            f"[RecurPay] Removed {len(placeholder_customers)} leftover example "
            f"customer(s) and {len(placeholder_subscriptions)} example subscription(s) "
            f"from {self.data_file} (one-time cleanup)."
        )

        self.data = data
        self._save_data()

        return data

    def _save_data(self):
        with open(self.data_file, "w") as f:
            # Serialize datetime objects and custom classes
            serializable_data = {
                "customers": [c.to_dict() for c in self.data["customers"]],
                "subscriptions": [s.to_dict() for s in self.data["subscriptions"]]
            }
            json.dump(serializable_data, f, indent=4)

    def add_customer(self, customer):
        self.data["customers"].append(customer)
        self._save_data()

    def get_customer(self, customer_id):
        for customer in self.data["customers"]:
            if customer.customer_id == customer_id:
                return customer
        return None

    def find_customers(self, query):
        """Look up customers by full ID, ID prefix, name, or email
        (case-insensitive substring). Returns a list so callers can
        detect zero/one/many matches. Falls back through match types
        in order of specificity: exact ID, ID prefix, then text search."""
        query = (query or "").strip()
        if not query:
            return []

        exact = [c for c in self.data["customers"] if c.customer_id == query]
        if exact:
            return exact

        prefix = [c for c in self.data["customers"] if c.customer_id.startswith(query)]
        if prefix:
            return prefix

        query_lower = query.lower()
        return [
            c for c in self.data["customers"]
            if query_lower in c.name.lower() or query_lower in c.email.lower()
        ]

    def update_customer(self, customer_id, new_name=None, new_email=None, **kwargs):
        for customer in self.data["customers"]:
            if customer.customer_id == customer_id:
                if new_name is not None:
                    customer.name = new_name
                if new_email is not None:
                    customer.email = new_email
                for key, value in kwargs.items():
                    setattr(customer, key, value)
                self._save_data()
                return True
        return False

    def delete_customer(self, customer_id):
        initial_len = len(self.data["customers"])
        self.data["customers"] = [c for c in self.data["customers"] if c.customer_id != customer_id]
        self.data["subscriptions"] = [s for s in self.data["subscriptions"] if s.customer_id != customer_id]
        if len(self.data["customers"]) < initial_len:
            self._save_data()
            return True
        return False

    def list_customers(self):
        return self.data["customers"]

    def add_subscription(self, subscription):
        self.data["subscriptions"].append(subscription)
        self._save_data()

    def get_subscription(self, subscription_id):
        for sub in self.data["subscriptions"]:
            if sub.subscription_id == subscription_id:
                return sub
        return None

    def find_subscriptions(self, query):
        """Look up subscriptions by full ID, ID prefix, description text,
        or the associated customer's name (case-insensitive substring).
        Returns a list so callers can detect zero/one/many matches."""
        query = (query or "").strip()
        if not query:
            return []

        exact = [s for s in self.data["subscriptions"] if s.subscription_id == query]
        if exact:
            return exact

        prefix = [s for s in self.data["subscriptions"] if s.subscription_id.startswith(query)]
        if prefix:
            return prefix

        query_lower = query.lower()
        matches = []
        for s in self.data["subscriptions"]:
            customer = self.get_customer(s.customer_id)
            customer_name = customer.name.lower() if customer else ""
            if query_lower in s.description.lower() or query_lower in customer_name:
                matches.append(s)
        return matches

    def update_subscription(self, subscription_id, **kwargs):
        for sub in self.data["subscriptions"]:
            if sub.subscription_id == subscription_id:
                for key, value in kwargs.items():
                    setattr(sub, key, value)
                self._save_data()
                return True
        return False

    def delete_subscription(self, subscription_id):
        initial_len = len(self.data["subscriptions"])
        self.data["subscriptions"] = [s for s in self.data["subscriptions"] if s.subscription_id != subscription_id]
        if len(self.data["subscriptions"]) < initial_len:
            self._save_data()
            return True
        return False

    def list_subscriptions(self):
        return self.data["subscriptions"]

    def get_subscriptions_by_customer(self, customer_id):
        return [s for s in self.data["subscriptions"] if s.customer_id == customer_id]
