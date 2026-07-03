import json
import os
from datetime import datetime
from config import DATA_FILE
from models import Customer, Subscription

class JSONStorage:
    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.data = self._load_data()

    def _load_data(self):
        if not os.path.exists(self.data_file):
            return {"customers": [], "subscriptions": []}
        with open(self.data_file, "r") as f:
            try:
                data = json.load(f)
                # Deserialize datetime objects
                data["customers"] = [Customer.from_dict(c) for c in data.get("customers", [])]
                data["subscriptions"] = [Subscription.from_dict(s) for s in data.get("subscriptions", [])]
                return data
            except json.JSONDecodeError:
                return {"customers": [], "subscriptions": []}

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
