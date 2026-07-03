RecurPay MVP

Subscription Payment Tracker for Nigerian Small Business Owners

RecurPay is a Minimum Viable Product (MVP) designed for the DevCareer x Nomba Hackathon 2026. It helps Nigerian small business owners manage recurring billing by assigning customer virtual accounts under one Nomba sub-account, tracking due dates, and reconciling recurring payments through each customer's accountRef. The application features a command-line interface (CLI) for core functionalities and a simple HTML dashboard for visual data representation.


Project Structure

The project is organized into the following files:



config.py: Stores Nomba API credentials and other application settings.

nomba_api.py: Handles integration with the Nomba API for authentication, customer virtual account lifecycle, balance checks, transaction reconciliation, checkout status, and checkout link generation, including a mock fallback mode.

models.py: Defines the data models for Customer and Subscription.

storage.py: Manages persistent data storage using a JSON file (data.json).

recurpay.py: The main CLI application that provides all backend features.

dashboard.html: A standalone HTML/CSS file for a simple frontend dashboard.

README.md: This project documentation.


Backend Features (Python CLI)

The recurpay.py CLI application provides the following features:



Customer Management: Allows users to add, edit, delete, and list customer records.

Customer Virtual Accounts: Creates a dedicated Nomba virtual account for each customer under the team's configured sub-account, using the customer ID as accountRef for reconciliation.

Nomba Reconciliation Tools: Lists virtual accounts, checks sub-account balance, and fetches account transactions so inflows can be matched to customers by accountRef.

Subscription/Billing Cycle Setup: Supports defining recurring payments with weekly, monthly, quarterly, yearly, custom (e.g., custom:7), or plain day-based intervals such as 90 days.

Due Date Tracking: Automatically tracks payment due dates and detects overdue payments.

Nomba Checkout Link Generation: Integrates with the Nomba API to generate unique checkout links for due payments. Includes a robust mock fallback mechanism when the API is unavailable or returns errors.

Payment Status Tracking: Manages payment statuses, including pending, paid, and overdue.

Payment Reminders List: Displays a list of subscriptions that are pending or overdue, indicating who needs to be reminded.

JSON File Storage: All customer and subscription data is persistently stored in data.json between sessions.

Rich Terminal Output: Utilizes the rich library for aesthetically pleasing and informative command-line output.


Nomba API Integration

RecurPay integrates with the Nomba API for secure authentication, virtual account collection, and optional checkout link generation. The key endpoints used are:



Authentication: POST https://sandbox.nomba.com/v1/auth/token/issue

Headers: Content-Type: application/json, accountId: <your_account_id>
Body: {"grant_type": "client_credentials", "client_id": "...", "client_secret": "..."}
The access_token is extracted from data["data"]["access_token"] in the response.

Virtual Account Creation: POST https://sandbox.nomba.com/v1/accounts/virtual/{subAccountId}

Headers: Authorization: Bearer <token>, Content-Type: application/json, accountId: <your_parent_account_id>
Body: Includes accountRef and accountName, with optional expectedAmount and expiryDate for one-time payment use cases.
The virtual account details are extracted from data["data"] in the response and stored against the customer.

Virtual Account List: POST https://sandbox.nomba.com/v1/accounts/virtual/list

Virtual Account Fetch/Expire: GET or DELETE https://sandbox.nomba.com/v1/accounts/virtual/{identifier}

Sub-account Balance: GET https://sandbox.nomba.com/v1/accounts/{subAccountId}/balance

Transaction Reconciliation: GET https://sandbox.nomba.com/v1/transactions/accounts/{subAccountId}

Transaction Requery: GET https://sandbox.nomba.com/v1/transactions/requery/{sessionId}

Checkout Link Generation: POST https://sandbox.nomba.com/v1/checkout/order

Headers: Authorization: Bearer <token>, Content-Type: application/json, accountId: <your_account_id>
Body: Includes order object with amount, currency (NGN), callbackUrl, customerEmail, orderReference, and optional orderMetaData.
The checkoutLink is extracted from data["data"]["checkoutLink"] in the response.

Checkout Status: GET https://sandbox.nomba.com/v1/checkout/order/{orderReference}


Mock/Fallback Mode

To ensure resilience and allow development despite potential API issues (e.g., 403 errors with shared hackathon credentials), nomba_api.py includes a mock fallback mode. If the Nomba API returns a 403 error, any other requests.exceptions.RequestException, or fails to return a valid token, checkout link, virtual account, balance, or transaction list, the system gracefully switches to mock mode. In this mode, placeholder checkout links, deterministic mock virtual account numbers, empty mock transaction lists, and zero-balance mock responses are generated, and a warning is printed to the console.


Architecture Note

RecurPay follows the hackathon-recommended hierarchy:

One Nomba Hackathon parent account -> one team sub-account -> many customer virtual accounts.

Each customer's RecurPay customer ID is used as accountRef. When Nomba sends a webhook or returns account transactions, RecurPay can match the accountRef back to the customer and record the payment against that customer's recurring subscription.


HTML Dashboard (dashboard.html)

The dashboard.html file provides a simple, standalone web interface to visualize the RecurPay data. It features:



Clean, Modern Design: A responsive layout suitable for mobile devices (e.g., Termux users).

Customer List: Displays all registered customers and their assigned virtual account details when available.

Upcoming & Overdue Payments: Highlights payments that are due soon or are already overdue (in red).

Payment History: Shows a record of paid subscriptions.

Data Loading: Loads data directly from the data.json file using JavaScript. To update the dashboard, simply run the CLI application to modify data.json and then refresh the dashboard.html page in a browser.


How to Run


Navigate to the project directory:
cd /home/ubuntu/recurpay

Install dependencies:
pip3 install -r requirements.txt

Run the CLI application:
python3 recurpay.py

View the Dashboard: Open dashboard.html in any web browser. To see updated data, ensure you've run the CLI to modify data.json and then refresh the browser page.


Important Notes


Termux Compatibility: The project is designed to be lightweight and runnable on Termux, using only standard Python libraries (requests, json, datetime, os) and rich for CLI aesthetics.

Standalone HTML: The dashboard.html is a self-contained file, making it easy to open and view without needing a web server.

Hackathon Ready: This MVP provides core functionalities and a clear demonstration of Nomba API integration (with fallback), fulfilling the hackathon requirements.



Built for the DevCareer x Nomba Hackathon 2026.
