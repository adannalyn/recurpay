import requests
import hashlib
import time
from datetime import datetime, timedelta
from config import NOMBA_ACCOUNT_ID, NOMBA_CLIENT_ID, NOMBA_CLIENT_SECRET, NOMBA_BASE_URL, NOMBA_CALLBACK_URL, DEBUG

try:
    from config import NOMBA_SUB_ACCOUNT_ID
except ImportError:
    NOMBA_SUB_ACCOUNT_ID = None

# Nomba's direct debit mandate API only accepts a fixed set of calendar
# cycles - it has no daily option and no arbitrary day-count frequencies,
# unlike RecurPay's own Subscription.frequency field (which also accepts
# things like "90 days" or "custom:7"). This maps the subset of RecurPay
# frequencies that have a clean Nomba equivalent; anything else (daily,
# plain day-counts, custom day-counts) has no mandate equivalent and
# should keep using checkout links instead.
_NOMBA_FREQUENCY_MAP = {
    "weekly": "WEEKLY", "week": "WEEKLY",
    "biweekly": "EVERY_TWO_WEEKS", "fortnightly": "EVERY_TWO_WEEKS",
    "monthly": "MONTHLY", "month": "MONTHLY",
    "quarterly": "EVERY_THREE_MONTHS", "quarter": "EVERY_THREE_MONTHS",
    "yearly": "EVERY_TWELVE_MONTHS", "annual": "EVERY_TWELVE_MONTHS",
    "annually": "EVERY_TWELVE_MONTHS", "year": "EVERY_TWELVE_MONTHS",
}


def frequency_to_nomba_enum(frequency):
    """Translate a RecurPay frequency string to Nomba's mandate frequency
    enum. Raises ValueError for frequencies with no clean equivalent."""
    key = frequency.strip().lower().replace("_", " ")
    if key in _NOMBA_FREQUENCY_MAP:
        return _NOMBA_FREQUENCY_MAP[key]
    raise ValueError(
        f"Frequency '{frequency}' isn't supported for direct debit mandates. "
        "Nomba's mandate API only supports fixed cycles: weekly, biweekly, monthly, "
        "quarterly, or yearly. Day-count frequencies like '90 days' or 'custom:7' "
        "aren't supported for auto-charge - use a checkout link for those instead."
    )


def generate_numeric_reference(seed):
    """Nomba requires merchantReference to be a numeric-only string, unique
    per transaction - RecurPay's own IDs are UUIDs, so this derives a
    numeric string from a seed plus the current time for uniqueness."""
    digest = hashlib.sha256(f"{seed}-{time.time()}".encode("utf-8")).hexdigest()
    return str(int(digest[:15], 16))[:15]

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

        missing = [
            name for name, value in (
                ("NOMBA_ACCOUNT_ID", self.account_id),
                ("NOMBA_CLIENT_ID", self.client_id),
                ("NOMBA_CLIENT_SECRET", self.client_secret),
                ("NOMBA_BASE_URL", self.base_url),
            ) if not value
        ]
        if missing:
            print(f"[NombaAPI Error] Missing required config: {', '.join(missing)}. "
                  f"Check your .env file. Switching to mock mode.")
            self.mock_mode = True
            return None

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
            try:
                data = response.json()
            except ValueError:
                data = {}
            if response.status_code == 403:
                desc = data.get("description") or data.get("message") or response.text[:200] or "No details returned by API."
                print(f"[NombaAPI Warning] API returned 403 Forbidden: {desc} Switching to mock mode.")
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

    # --- Direct Debit Mandates -----------------------------------------
    # Field names here follow Nomba's published OpenAPI schema for
    # POST /v1/direct-debits, which uses a different response envelope
    # (responseCode/responseMessage) than most other endpoints in this
    # file (code/description). Get Mandate Status and Debit a Mandate
    # aren't fully documented publicly at the time of writing, so their
    # exact field names are a best-effort match to the same conventions -
    # worth double-checking against a live response once auth is working.

    def create_direct_debit_mandate(self, customer_account_number, bank_code, customer_name,
                                     customer_account_name, customer_email, customer_phone_number,
                                     amount, frequency, start_date, end_date, merchant_reference,
                                     customer_address="", narration=""):
        """Create a direct debit mandate. The customer must still complete
        a one-time bank authorization step (Nomba returns instructions,
        typically a small token payment) before the mandate can be used."""
        if self.mock_mode:
            print("[NombaAPI Warning] Nomba API is in mock mode. Generating mock mandate.")
            return self._mock_mandate(merchant_reference, customer_phone_number)

        token = self._get_access_token()
        if not token:
            self.mock_mode = True
            print("[NombaAPI Warning] Could not get access token. Falling back to mock mandate.")
            return self._mock_mandate(merchant_reference, customer_phone_number)

        url = f"{self.base_url}/direct-debits"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accountId": self.account_id
        }
        payload = {
            "customerAccountNumber": customer_account_number,
            "bankCode": bank_code,
            "customerName": customer_name,
            "customerAddress": customer_address,
            "customerAccountName": customer_account_name,
            "amount": float(amount),
            "frequency": frequency,
            "narration": narration or f"RecurPay mandate {merchant_reference}",
            "customerPhoneNumber": customer_phone_number,
            "merchantReference": merchant_reference,
            "startDate": start_date,
            "endDate": end_date,
            "customerEmail": customer_email,
            "startImmediately": True
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            try:
                data = response.json()
            except ValueError:
                data = {}
            if response.status_code == 403:
                desc = data.get("description") or data.get("responseMessage") or response.text[:200] or "No details returned."
                print(f"[NombaAPI Warning] API returned 403 Forbidden: {desc} Switching to mock mode.")
                self.mock_mode = True
                return self._mock_mandate(merchant_reference, customer_phone_number)

            if data.get("responseCode") == "00" and isinstance(data.get("data"), dict):
                if DEBUG: print(f"[NombaAPI] Mandate created: {data['data'].get('mandateId')}")
                return data["data"]

            desc = data.get("responseMessage") or data.get("description", "Unknown error")
            print(f"[NombaAPI Error] Failed to create mandate: {desc}")
            self.mock_mode = True
            return self._mock_mandate(merchant_reference, customer_phone_number)
        except requests.exceptions.RequestException as e:
            print(f"[NombaAPI Error] Network or API error during mandate creation: {e}")
            self.mock_mode = True
            return self._mock_mandate(merchant_reference, customer_phone_number)

    def get_mandate_status(self, mandate_id):
        return self._send_authenticated_request(
            "get",
            f"/direct-debits/{mandate_id}",
            f"fetch mandate status for {mandate_id}",
            fallback={"mandateId": mandate_id, "status": "ACTIVE", "mock": True}
        )

    def debit_mandate(self, mandate_id, amount, reference, narration=""):
        """Charge a customer using an already-activated mandate."""
        if self.mock_mode:
            print("[NombaAPI Warning] Nomba API is in mock mode. Generating mock debit result.")
            return self._mock_debit(mandate_id, amount, reference)

        token = self._get_access_token()
        if not token:
            self.mock_mode = True
            print("[NombaAPI Warning] Could not get access token. Falling back to mock debit.")
            return self._mock_debit(mandate_id, amount, reference)

        url = f"{self.base_url}/direct-debits/debit-mandate"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accountId": self.account_id
        }
        payload = {
            "mandateId": mandate_id,
            "amount": float(amount),
            "merchantReference": reference,
            "narration": narration or f"RecurPay charge {reference}"
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            try:
                data = response.json()
            except ValueError:
                data = {}
            if response.status_code == 403:
                desc = data.get("description") or data.get("responseMessage") or response.text[:200] or "No details returned."
                print(f"[NombaAPI Warning] API returned 403 Forbidden: {desc} Switching to mock mode.")
                self.mock_mode = True
                return self._mock_debit(mandate_id, amount, reference)

            success_code = data.get("responseCode") == "00" or data.get("code") == "00"
            if success_code and isinstance(data.get("data"), dict):
                if DEBUG: print(f"[NombaAPI] Mandate {mandate_id} debited successfully.")
                return data["data"]

            desc = data.get("responseMessage") or data.get("description", "Unknown error")
            print(f"[NombaAPI Error] Failed to debit mandate {mandate_id}: {desc}")
            self.mock_mode = True
            return self._mock_debit(mandate_id, amount, reference)
        except requests.exceptions.RequestException as e:
            print(f"[NombaAPI Error] Network or API error while debiting mandate {mandate_id}: {e}")
            self.mock_mode = True
            return self._mock_debit(mandate_id, amount, reference)

    def _mock_mandate(self, merchant_reference, phone_number):
        digest = hashlib.sha256(str(merchant_reference).encode("utf-8")).hexdigest()
        mandate_id = f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
        return {
            "mandateId": mandate_id,
            "merchantReference": merchant_reference,
            "phoneNumber": phone_number,
            "description": (
                "MOCK MANDATE - Nomba API is not authenticating right now. In a real "
                "mandate, the customer would need to pay a small token amount into a "
                "specific NIBSS account to authorize it. This mock mandate is treated "
                "as immediately active for demo purposes."
            ),
            "status": "ACTIVE",
            "mock": True
        }

    def _mock_debit(self, mandate_id, amount, reference):
        return {
            "mandateId": mandate_id,
            "merchantReference": reference,
            "amount": f"{float(amount):.2f}",
            "status": "successful",
            "mock": True
        }

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