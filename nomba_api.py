import requests
import json
from datetime import datetime, timedelta
from config import NOMBA_ACCOUNT_ID, NOMBA_CLIENT_ID, NOMBA_CLIENT_SECRET, NOMBA_BASE_URL, DEBUG

class NombaAPI:
    def __init__(self):
        self.account_id = NOMBA_ACCOUNT_ID
        self.client_id = NOMBA_CLIENT_ID
        self.client_secret = NOMBA_CLIENT_SECRET
        self.base_url = NOMBA_BASE_URL
        self.access_token = None
        self.token_expiry = None
        self.mock_mode = False

    def _get_access_token(self):
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        auth_url = f"https://sandbox.nomba.com/v1/auth/token/issue" # Use the correct sandbox auth URL
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
                "callbackUrl": "https://eo5h6zze4pfeyfn.m.pipedream.net",
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
