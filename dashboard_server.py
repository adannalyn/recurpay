"""
RecurPay Dashboard Server

A minimal, stdlib-only local web server that:
  1. Serves dashboard.html (and any other file in this folder) as normal
     static files over http:// - which fixes the file:// fetch/CORS
     restriction outright, since fetch() works fine for same-origin
     http(s) requests.
  2. Exposes a small JSON API under /api/... that reads and writes through
     the existing JSONStorage/Customer/Subscription classes, so the CLI
     and the browser dashboard share exactly one source of truth
     (data.json) and one set of business rules - nothing is duplicated.

Run it with:
    python3 dashboard_server.py [port]

Then open:
    http://localhost:8000/dashboard.html

No third-party packages required - only Python's standard library.
"""

import datetime
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from storage import JSONStorage
from models import Customer, Subscription
from nomba_api import NombaAPI, frequency_to_nomba_enum, generate_numeric_reference

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VALID_STATUSES = ("pending", "paid", "overdue")

# One shared instance, same as recurpay.py's module-level nomba_api - this
# lets mock_mode persist sensibly across requests instead of re-detecting
# auth failure on every single call.
nomba_api = NombaAPI()


def is_mock_result(result):
    """True if a Nomba API call's result came from the mock fallback path,
    either because mock_mode is already latched on, or because this
    particular result dict says so."""
    return nomba_api.mock_mode or (isinstance(result, dict) and result.get("mock"))


class DashboardRequestHandler(BaseHTTPRequestHandler):
    # --- small helpers -----------------------------------------------

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status, message):
        self._send_json(status, {"error": message})

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _serve_static_file(self):
        # Only ever serve files that live inside this project folder -
        # reject any attempt to escape it (e.g. "..") before touching disk.
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            path = "/dashboard.html"

        requested = os.path.normpath(os.path.join(ROOT_DIR, path.lstrip("/")))
        if not requested.startswith(ROOT_DIR) or not os.path.isfile(requested):
            self._send_error_json(404, f"Not found: {path}")
            return

        content_types = {
            ".html": "text/html", ".json": "application/json",
            ".js": "application/javascript", ".css": "text/css",
        }
        ext = os.path.splitext(requested)[1]
        content_type = content_types.get(ext, "application/octet-stream")

        with open(requested, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- routing -------------------------------------------------------

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/data":
                storage = JSONStorage()
                self._send_json(200, {
                    "customers": [c.to_dict() for c in storage.list_customers()],
                    "subscriptions": [s.to_dict() for s in storage.list_subscriptions()],
                })
                return
            if path == "/api/nomba/balance":
                balance = nomba_api.get_sub_account_balance()
                self._send_json(200, {"balance": balance, "mock": is_mock_result(balance)})
                return
            self._serve_static_file()
        except Exception as e:
            self._send_error_json(500, str(e))

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        parts = path.strip("/").split("/")
        try:
            if path == "/api/customers":
                self._create_customer()
                return
            if path == "/api/subscriptions":
                self._create_subscription()
                return
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "customers" and parts[3] == "virtual-account":
                self._create_virtual_account(parts[2])
                return
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "subscriptions" and parts[3] == "checkout-link":
                self._create_checkout_link(parts[2])
                return
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "customers" and parts[3] == "mandate":
                self._create_mandate(parts[2])
                return
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "subscriptions" and parts[3] == "charge":
                self._charge_via_mandate(parts[2])
                return
            self._send_error_json(404, f"Unknown endpoint: {path}")
        except Exception as e:
            self._send_error_json(500, str(e))

    def do_PATCH(self):
        parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
        try:
            if len(parts) == 3 and parts[:2] == ["api", "subscriptions"]:
                self._update_subscription_status(parts[2])
                return
            self._send_error_json(404, "Unknown endpoint")
        except Exception as e:
            self._send_error_json(500, str(e))

    def do_DELETE(self):
        parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
        try:
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "customers" and parts[3] == "virtual-account":
                self._delete_virtual_account(parts[2])
                return
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "customers" and parts[3] == "mandate":
                storage = JSONStorage()
                customer = storage.get_customer(parts[2])
                if not customer:
                    self._send_error_json(404, "Customer not found.")
                    return
                if not (customer.direct_debit_mandate or {}).get("mandateId"):
                    self._send_error_json(400, "This customer has no mandate to clear.")
                    return
                storage.update_customer(parts[2], direct_debit_mandate={})
                self._send_json(200, {"deleted": True})
                return
            if len(parts) == 3 and parts[:2] == ["api", "customers"]:
                storage = JSONStorage()
                if storage.delete_customer(parts[2]):
                    self._send_json(200, {"deleted": True})
                else:
                    self._send_error_json(404, "Customer not found")
                return
            if len(parts) == 3 and parts[:2] == ["api", "subscriptions"]:
                storage = JSONStorage()
                if storage.delete_subscription(parts[2]):
                    self._send_json(200, {"deleted": True})
                else:
                    self._send_error_json(404, "Subscription not found")
                return
            self._send_error_json(404, "Unknown endpoint")
        except Exception as e:
            self._send_error_json(500, str(e))

    # --- action handlers -------------------------------------------------

    def _create_customer(self):
        body = self._read_json_body()
        name = (body.get("name") or "").strip()
        email = (body.get("email") or "").strip()
        if not name or not email:
            self._send_error_json(400, "Both name and email are required.")
            return
        storage = JSONStorage()
        customer = Customer(name, email)
        storage.add_customer(customer)
        self._send_json(201, customer.to_dict())

    def _create_subscription(self):
        body = self._read_json_body()
        storage = JSONStorage()
        customer = storage.get_customer(body.get("customer_id", ""))
        if not customer:
            self._send_error_json(404, "Customer not found.")
            return

        try:
            amount = float(body.get("amount"))
        except (TypeError, ValueError):
            self._send_error_json(400, "Amount must be a number.")
            return

        frequency = (body.get("frequency") or "").strip()
        description = (body.get("description") or "").strip()
        start_date_str = body.get("start_date") or datetime.date.today().isoformat()
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            self._send_error_json(400, "start_date must be in YYYY-MM-DD format.")
            return

        try:
            subscription = Subscription(customer.customer_id, amount, frequency, start_date, description)
        except ValueError as e:
            self._send_error_json(400, str(e))
            return

        storage.add_subscription(subscription)
        self._send_json(201, subscription.to_dict())

    def _create_virtual_account(self, customer_id):
        storage = JSONStorage()
        customer = storage.get_customer(customer_id)
        if not customer:
            self._send_error_json(404, "Customer not found.")
            return

        existing = customer.virtual_account or {}
        if existing.get("bankAccountNumber"):
            self._send_error_json(400, "This customer already has a virtual account. Remove it first.")
            return

        virtual_account = nomba_api.create_virtual_account_for_sub_account(
            account_ref=customer.customer_id,
            account_name=customer.name
        )
        if not virtual_account:
            self._send_error_json(502, "Failed to create virtual account.")
            return

        storage.update_customer(customer_id, virtual_account=virtual_account)
        self._send_json(201, {
            "customer": storage.get_customer(customer_id).to_dict(),
            "mock": is_mock_result(virtual_account),
        })

    def _delete_virtual_account(self, customer_id):
        storage = JSONStorage()
        customer = storage.get_customer(customer_id)
        if not customer:
            self._send_error_json(404, "Customer not found.")
            return

        virtual_account = customer.virtual_account or {}
        if not virtual_account.get("bankAccountNumber"):
            self._send_error_json(400, "This customer has no virtual account to remove.")
            return

        identifier = virtual_account.get("accountRef", customer.customer_id)
        was_mock = nomba_api.mock_mode
        result = nomba_api.expire_virtual_account(identifier)

        # Same rule as the CLI: the local record is authoritative for the
        # virtual_account slot regardless of whether Nomba's servers
        # confirm the expiry, so it's always cleared here.
        storage.update_customer(customer_id, virtual_account={})

        self._send_json(200, {
            "deleted": True,
            "mock": was_mock or is_mock_result(result),
        })

    def _create_checkout_link(self, subscription_id):
        storage = JSONStorage()
        subscription = storage.get_subscription(subscription_id)
        if not subscription:
            self._send_error_json(404, "Subscription not found.")
            return

        customer = storage.get_customer(subscription.customer_id)
        if not customer:
            self._send_error_json(404, "Associated customer not found.")
            return

        order_ref = f"RECURPAY-{subscription.subscription_id}"
        checkout_link = nomba_api.generate_checkout_link(
            subscription.amount, customer.email, order_ref, subscription.description
        )
        if not checkout_link:
            self._send_error_json(502, "Failed to generate checkout link.")
            return

        storage.update_subscription(subscription_id, checkout_link=checkout_link)
        is_mock = nomba_api.mock_mode or checkout_link.startswith("https://mock-checkout.nomba.com/")
        self._send_json(200, {
            "subscription": storage.get_subscription(subscription_id).to_dict(),
            "mock": is_mock,
        })

    def _create_mandate(self, customer_id):
        storage = JSONStorage()
        customer = storage.get_customer(customer_id)
        if not customer:
            self._send_error_json(404, "Customer not found.")
            return

        body = self._read_json_body()
        required = ["account_number", "bank_code", "phone_number", "amount", "frequency"]
        missing = [f for f in required if not body.get(f)]
        if missing:
            self._send_error_json(400, f"Missing required fields: {', '.join(missing)}")
            return

        try:
            nomba_frequency = frequency_to_nomba_enum(body["frequency"])
        except ValueError as e:
            self._send_error_json(400, str(e))
            return

        try:
            amount = float(body["amount"])
        except (TypeError, ValueError):
            self._send_error_json(400, "Amount must be a number.")
            return

        duration_months = int(body.get("duration_months", 12) or 12)
        start_date = datetime.datetime.now()
        end_date = start_date + datetime.timedelta(days=30 * duration_months)
        merchant_reference = generate_numeric_reference(customer.customer_id)

        mandate = nomba_api.create_direct_debit_mandate(
            customer_account_number=body["account_number"],
            bank_code=body["bank_code"],
            customer_name=customer.name,
            customer_account_name=customer.name,
            customer_email=customer.email,
            customer_phone_number=body["phone_number"],
            amount=amount,
            frequency=nomba_frequency,
            start_date=start_date.strftime("%Y-%m-%dT%H:%M"),
            end_date=end_date.strftime("%Y-%m-%dT%H:%M"),
            merchant_reference=merchant_reference,
            customer_address=body.get("address", "")
        )
        if not mandate:
            self._send_error_json(502, "Failed to create mandate.")
            return

        storage.update_customer(customer_id, direct_debit_mandate=mandate)
        self._send_json(201, {
            "customer": storage.get_customer(customer_id).to_dict(),
            "mock": is_mock_result(mandate),
        })

    def _charge_via_mandate(self, subscription_id):
        storage = JSONStorage()
        subscription = storage.get_subscription(subscription_id)
        if not subscription:
            self._send_error_json(404, "Subscription not found.")
            return

        customer = storage.get_customer(subscription.customer_id)
        if not customer:
            self._send_error_json(404, "Associated customer not found.")
            return

        mandate = customer.direct_debit_mandate or {}
        mandate_id = mandate.get("mandateId")
        if not mandate_id:
            self._send_error_json(400, "This customer has no direct debit mandate set up yet.")
            return

        reference = generate_numeric_reference(subscription.subscription_id)
        result = nomba_api.debit_mandate(mandate_id, subscription.amount, reference, subscription.description)
        if not result:
            self._send_error_json(502, "Failed to charge mandate.")
            return

        status = str(result.get("status", "")).lower()
        if status not in ("successful", "success"):
            self._send_error_json(502, f"Charge did not succeed. Status: {result.get('status', 'unknown')}")
            return

        subscription.last_payment_date = datetime.datetime.now()
        subscription.update_next_due_date()
        storage.update_subscription(
            subscription_id,
            status="paid",
            last_payment_date=subscription.last_payment_date,
            next_due_date=subscription.next_due_date
        )
        self._send_json(200, {
            "subscription": storage.get_subscription(subscription_id).to_dict(),
            "mock": is_mock_result(result),
        })

    def _update_subscription_status(self, subscription_id):
        body = self._read_json_body()
        new_status = body.get("status")
        if new_status not in VALID_STATUSES:
            self._send_error_json(400, f"status must be one of {VALID_STATUSES}.")
            return

        storage = JSONStorage()
        subscription = storage.get_subscription(subscription_id)
        if not subscription:
            self._send_error_json(404, "Subscription not found.")
            return

        updates = {"status": new_status}
        if new_status == "paid":
            subscription.last_payment_date = datetime.datetime.now()
            subscription.update_next_due_date()
            updates["last_payment_date"] = subscription.last_payment_date
            updates["next_due_date"] = subscription.next_due_date

        storage.update_subscription(subscription_id, **updates)
        self._send_json(200, subscription.to_dict())

    # Quiet down the default per-request stderr logging a little.
    def log_message(self, format_str, *args):
        sys.stderr.write("[dashboard_server] " + (format_str % args) + "\n")


def run(port=8000):
    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardRequestHandler)
    print(f"RecurPay dashboard server running - open http://localhost:{port}/dashboard.html")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    chosen_port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run(chosen_port)