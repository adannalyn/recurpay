import requests
import hashlib
from datetime import datetime, timedelta
from config import NOMBA_ACCOUNT_ID, NOMBA_CLIENT_ID, NOMBA_CLIENT_SECRET, NOMBA_BASE_URL, NOMBA_CALLBACK_URL, DEBUG

try:
    from config import NOMBA_SUB_ACCOUNT_ID
except ImportError:
    NOMBA_SUB_ACCOUNT_ID = None

class NombaAPI:
    def __init__(self):
        self.account_id = NOMBA_ACCOUNT_ID
        self.client_id = NOMBA_CLIENT_ID
        self.client_secret = NOMBA_CLIENT_SECRET
        self.base_url = NOMBA_BASE_URL
        self.sub_account_id = NOMBA_SUB_ACCOUNT_ID
        self.access_token = None
        self.token_expiry = None
        self.mock_mode = False

    def _get_access_token(self):
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        auth_url = f"{self.base_url}/auth/token/issue"
        headers = {
            "Content-Type": "application/json",
            "accountId": self.account_id
        }
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        try:
            response = requests.post(auth_url, headers=headers, json=payload)
            data = response.json()
            if response.status_code == 403:
                print(f"[NombaAPI Warning] API returned 403 Forbidden. Switching to mock mode.")
                self.mock_mode = True
                return None
            if data.get("code") == "00" and "access_token" in data.get("data", {}):
                self.access_token = data["data"]["access_token"]
                expires_in = data["data"].get("expires_in", 3600) # Default to 1 hour
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60) # Refresh 1 minute before expiry
                self.mock_mode = False
                if DEBUG: print("[NombaAPI] Successfully obtained access token.")
                return self.access_token
            else:
                desc = data.get('description', 'Unknown error')
                print(f"[NombaAPI Error] Failed to get access token: {desc}")
                self.mock_mode = True
                return None
        except requests.exceptions.RequestException as e:
            print(f"[NombaAPI Error] Network or API error during authentication: {e}")
            self.mock_mode = True
            return None

    def generate_checkout_link(self, amount, customer_email, order_reference, description=""): # Added description parameter
        if self.mock_mode:
            print("[NombaAPI Warning] Nomba API is in mock mode. Generating placeholder checkout link.")
            return f"https://mock-checkout.nomba.com/pay/{order_reference}?amount={amount}"

        token = self._get_access_token()
        if not token:
            self.mock_mode = True
            print("[NombaAPI Warning] Could not get access token. Falling back to mock mode. Generating placeholder checkout link.")
            return f"https://mock-checkout.nomba.com/pay/{order_reference}?amount={amount}"

        checkout_url = f"{self.base_url}/checkout/order"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accountId": self.account_id
        }
        payload = {
            "order": {
                "amount": int(amount * 100),
                "currency": "NGN",
                "callbackUrl": NOMBA_CALLBACK_URL,
                "customerEmail": customer_email,
                "orderReference": order_reference,
                "orderMetaData": {"description": description} # Pass description as metadata
            }
        }

        try:
            response = requests.post(checkout_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == "00" and "checkoutLink" in data.get("data", {}):
                if DEBUG: print(f"[NombaAPI] Successfully generated checkout link for {order_reference}.")
                return data["data"]["checkoutLink"]
            else:
                desc = data.get('description', 'Unknown error')
                print(f"[NombaAPI Error] Failed to generate checkout link for {order_reference}: {desc}")
                self.mock_mode = True
                return f"https://mock-checkout.nomba.com/pay/{order_reference}?amount={amount}"
        except requests.exceptions.RequestException as e:
            print(f"[NombaAPI Error] Network or API error during checkout link generation for {order_reference}: {e}")
            self.mock_mode = True
            return f"https://mock-checkout.nomba.com/pay/{order_reference}?amount={amount}"

    def get_checkout_order_status(self, order_reference):
        return self._send_authenticated_request(
            "get",
            f"/checkout/order/{order_reference}",
            f"fetch checkout order status for {order_reference}",
            fallback={"orderReference": order_reference, "status": "unknown", "mock": True}
        )

    def create_virtual_account_for_sub_account(self, account_ref, account_name, expected_amount=None, expiry_date=None, bvn=None):
        account_name = self._format_account_name(account_name)

        if not self.sub_account_id:
            print("[NombaAPI Warning] No sub-account ID configured. Generating mock virtual account.")
            return self._mock_virtual_account(account_ref, account_name, expected_amount, expiry_date)

        if self.mock_mode:
            print("[NombaAPI Warning] Nomba API is in mock mode. Generating mock virtual account.")
            return self._mock_virtual_account(account_ref, account_name, expected_amount, expiry_date)

        token = self._get_access_token()
        if not token:
            self.mock_mode = True
            print("[NombaAPI Warning] Could not get access token. Falling back to mock virtual account.")
            return self._mock_virtual_account(account_ref, account_name, expected_amount, expiry_date)

        virtual_account_url = f"{self.base_url}/accounts/virtual/{self.sub_account_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accountId": self.account_id
        }
        payload = {
            "accountRef": account_ref,
            "accountName": account_name
        }

        if bvn:
            payload["bvn"] = bvn
        if expected_amount is not None:
            payload["expectedAmount"] = f"{float(expected_amount):.2f}"
        if expiry_date:
            payload["expiryDate"] = self._format_expiry_date(expiry_date)

        try:
            response = requests.post(virtual_account_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == "00" and isinstance(data.get("data"), dict):
                if DEBUG: print(f"[NombaAPI] Successfully created virtual account for {account_ref}.")
                return data["data"]

            desc = data.get("description", "Unknown error")
            print(f"[NombaAPI Error] Failed to create virtual account for {account_ref}: {desc}")
            self.mock_mode = True
            return self._mock_virtual_account(account_ref, account_name, expected_amount, expiry_date)
        except requests.exceptions.RequestException as e:
            print(f"[NombaAPI Error] Network or API error during virtual account creation for {account_ref}: {e}")
            self.mock_mode = True
            return self._mock_virtual_account(account_ref, account_name, expected_amount, expiry_date)

    def list_virtual_accounts(self, filters=None):
        return self._send_authenticated_request(
            "post",
            "/accounts/virtual/list",
            "list virtual accounts",
            payload=filters or {},
            fallback={"virtualAccounts": [], "mock": True}
        )

    def fetch_virtual_account(self, identifier):
        return self._send_authenticated_request(
            "get",
            f"/accounts/virtual/{identifier}",
            f"fetch virtual account {identifier}",
            fallback={"identifier": identifier, "mock": True}
        )

    def expire_virtual_account(self, identifier):
        return self._send_authenticated_request(
            "delete",
            f"/accounts/virtual/{identifier}",
            f"expire virtual account {identifier}",
            fallback={"identifier": identifier, "expired": False, "mock": True}
        )

    def get_sub_account_balance(self):
        if not self.sub_account_id:
            print("[NombaAPI Warning] No sub-account ID configured. Returning mock balance.")
            return self._mock_balance()

        return self._send_authenticated_request(
            "get",
            f"/accounts/{self.sub_account_id}/balance",
            "fetch sub-account balance",
            fallback=self._mock_balance()
        )

    def list_sub_account_transactions(self, filters=None):
        if not self.sub_account_id:
            print("[NombaAPI Warning] No sub-account ID configured. Returning mock transaction list.")
            return self._mock_transactions()

        return self._send_authenticated_request(
            "get",
            f"/transactions/accounts/{self.sub_account_id}",
            "list sub-account transactions",
            params=filters or {},
            fallback=self._mock_transactions()
        )

    def requery_transaction(self, session_id):
        return self._send_authenticated_request(
            "get",
            f"/transactions/requery/{session_id}",
            f"requery transaction {session_id}",
            fallback={"sessionId": session_id, "status": "unknown", "mock": True}
        )

    def _send_authenticated_request(self, method, path, action, payload=None, params=None, fallback=None):
        if self.mock_mode:
            print(f"[NombaAPI Warning] Nomba API is in mock mode. Using mock response for {action}.")
            return fallback

        token = self._get_access_token()
        if not token:
            self.mock_mode = True
            print(f"[NombaAPI Warning] Could not get access token. Using mock response for {action}.")
            return fallback

        request_method = getattr(requests, method.lower())
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accountId": self.account_id
        }

        try:
            response = request_method(url, headers=headers, json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == "00":
                return data.get("data", data)

            desc = data.get("description", "Unknown error")
            print(f"[NombaAPI Error] Failed to {action}: {desc}")
            self.mock_mode = True
            return fallback
        except requests.exceptions.RequestException as e:
            print(f"[NombaAPI Error] Network or API error while trying to {action}: {e}")
            self.mock_mode = True
            return fallback

    def _format_account_name(self, account_name):
        name = " ".join(str(account_name).split()).strip()
        if len(name) < 8:
            name = f"{name} RecurPay".strip()
        return name[:64]

    def _format_expiry_date(self, expiry_date):
        if isinstance(expiry_date, datetime):
            return expiry_date.strftime("%Y-%m-%d %H:%M:%S")
        return str(expiry_date)

    def _mock_virtual_account(self, account_ref, account_name, expected_amount=None, expiry_date=None):
        digest = hashlib.sha256(str(account_ref).encode("utf-8")).hexdigest()
        account_suffix = int(digest[:12], 16) % 1_000_000_000
        virtual_account = {
            "accountRef": account_ref,
            "accountName": account_name,
            "currency": "NGN",
            "bankName": "Nombank MFB",
            "bankAccountNumber": f"9{account_suffix:09d}",
            "bankAccountName": f"Nomba/{account_name}",
            "expired": False,
            "mock": True
        }
        if expected_amount is not None:
            virtual_account["expectedAmount"] = f"{float(expected_amount):.2f}"
        if expiry_date:
            virtual_account["expiryDate"] = self._format_expiry_date(expiry_date)
        return virtual_account

    def _mock_balance(self):
        return {
            "availableBalance": "0.00",
            "ledgerBalance": "0.00",
            "currency": "NGN",
            "mock": True
        }

    def _mock_transactions(self):
        return {
            "transactions": [],
            "mock": True
        }

# Example Usage (for testing)
if __name__ == "__main__":
    nomba_api = NombaAPI()
    # Test authentication
    print("\n--- Testing Authentication ---")
    token = nomba_api._get_access_token()
    if token:
        print(f"Access Token: {token[:10]}...")
    else:
        print("Failed to get access token.")

    # Test checkout link generation
    print("\n--- Testing Checkout Link Generation ---")
    test_amount = 5000.00
    test_email = "test@example.com"
    test_order_ref = "test-order-123"
    test_description = "Monthly Subscription"
    checkout_link = nomba_api.generate_checkout_link(test_amount, test_email, test_order_ref, test_description)
    print(f"Generated Checkout Link: {checkout_link}")

    # Simulate API failure by invalidating token (for testing mock mode)
    print("\n--- Simulating API Failure (Mock Mode Test) ---")
    nomba_api.access_token = "invalid_token"
    nomba_api.token_expiry = datetime.now() - timedelta(minutes=5) # Expire token
    checkout_link_mock = nomba_api.generate_checkout_link(test_amount, test_email, "test-order-mock", "Mock Subscription")
    print(f"Generated Mock Checkout Link: {checkout_link_mock}")
