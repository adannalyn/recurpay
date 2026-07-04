# RecurPay MVP

**Subscription Payment Tracker for Nigerian Small Business Owners**

RecurPay is a Minimum Viable Product (MVP) built for the DevCareer x Nomba Hackathon 2026. It helps Nigerian small business owners manage recurring payments by assigning each customer a dedicated Nomba virtual account under a single team sub-account, tracking subscription due dates, and reconciling payments using each customer's `accountRef`.

The project provides a command-line interface (CLI) for managing customers and subscriptions, along with a lightweight HTML dashboard for viewing customer and payment data.

---

# Project Structure

* **config.py** – Loads application configuration from environment variables and exposes settings used throughout the application.
* **.env.example** – Template containing the required environment variables.
* **nomba_api.py** – Handles authentication, virtual account management, balance checks, transaction reconciliation, checkout link generation, checkout status checks, and mock fallback behavior.
* **models.py** – Defines the Customer and Subscription data models.
* **storage.py** – Handles persistent JSON storage.
* **recurpay.py** – Main CLI application.
* **dashboard.html** – Standalone HTML dashboard for visualizing customer and subscription data.
* **data.example.json** – Sample data structure used to initialize local storage.
* **README.md** – Project documentation.

---

# Backend Features (CLI)

The CLI provides the following functionality:

* Create, edit, delete, and list customers.
* Generate a dedicated Nomba virtual account for every customer under the configured sub-account.
* Reconcile payments using each customer's `accountRef`.
* View customer virtual accounts.
* Check the configured sub-account balance.
* Retrieve account transactions.
* Create recurring subscriptions using weekly, monthly, quarterly, yearly, custom, or day-based billing intervals.
* Automatically track upcoming and overdue payments.
* Generate Nomba checkout links for pending payments.
* Track payment status (Pending, Paid, Overdue).
* Display subscriptions requiring payment reminders.
* Persist customer and subscription data locally using JSON.
* Display formatted CLI output using the `rich` library.

---

# Nomba API Integration

RecurPay integrates with the Nomba Sandbox API for authentication, virtual account management, transaction reconciliation, and checkout generation.

### Authentication

**POST**

`https://sandbox.nomba.com/v1/auth/token/issue`

Headers:

* `Content-Type: application/json`
* `accountId: <your_parent_account_id>`

Request Body:

```json
{
  "grant_type": "client_credentials",
  "client_id": "<your_client_id>",
  "client_secret": "<your_client_secret>"
}
```

The application extracts the access token from:

```text
data["data"]["access_token"]
```

---

### Virtual Account Creation

**POST**

`https://sandbox.nomba.com/v1/accounts/virtual/{subAccountId}`

Headers:

* `Authorization: Bearer <access_token>`
* `Content-Type: application/json`
* `accountId: <your_parent_account_id>`

The request includes:

* `accountRef`
* `accountName`

Optional fields include:

* `expectedAmount`
* `expiryDate`

Virtual account details are extracted from:

```text
data["data"]
```

and stored against the customer.

---

### Additional Endpoints

Virtual Account List

```
POST /accounts/virtual/list
```

Virtual Account Fetch

```
GET /accounts/virtual/{identifier}
```

Virtual Account Expire

```
DELETE /accounts/virtual/{identifier}
```

Sub-account Balance

```
GET /accounts/{subAccountId}/balance
```

Transaction Reconciliation

```
GET /transactions/accounts/{subAccountId}
```

Transaction Requery

```
GET /transactions/requery/{sessionId}
```

Checkout Link Generation

```
POST /checkout/order
```

Headers:

* `Authorization: Bearer <access_token>`
* `Content-Type: application/json`
* `accountId: <your_parent_account_id>`

The request includes:

* amount
* currency (NGN)
* callbackUrl
* customerEmail
* orderReference
* optional orderMetaData

The checkout URL is extracted from:

```text
data["data"]["checkoutLink"]
```

Checkout Status

```
GET /checkout/order/{orderReference}
```

---

# Mock / Fallback Mode

To ensure the application remains usable when the Nomba Sandbox API is unavailable, RecurPay automatically switches to mock mode whenever authentication fails, a request returns HTTP 403, another request exception occurs, or required API data cannot be retrieved.

Mock mode generates:

* Placeholder checkout links
* Deterministic virtual account numbers
* Empty transaction lists
* Zero-balance responses

A warning is displayed so the user knows the application is running without live API responses.

---

# Architecture

The application follows the recommended hackathon hierarchy:

```
Parent Account
    │
    └── Team Sub-account
            │
            ├── Customer Virtual Account
            ├── Customer Virtual Account
            └── Customer Virtual Account
```

Each customer's RecurPay customer ID is used as the Nomba `accountRef`. Incoming transactions or webhook events can therefore be matched directly to the correct customer and subscription.

---

# HTML Dashboard

The standalone dashboard provides a simple interface for viewing application data.

Features include:

* Responsive layout
* Customer list
* Virtual account information
* Upcoming payments
* Overdue payments
* Payment history

The dashboard reads data from the local `data.json` file. After making changes through the CLI, refresh the page to display the latest information.

---

# Environment Variables

Copy the example environment file before running the project.

```bash
cp .env.example .env
```

Configure the following variables in your local `.env` file:

* `NOMBA_ACCOUNT_ID`
* `NOMBA_SUB_ACCOUNT_ID`
* `NOMBA_CLIENT_ID`
* `NOMBA_CLIENT_SECRET`
* `NOMBA_BASE_URL`

The `.env` file contains sensitive credentials and should never be committed to version control.

---

# Data Storage

Runtime customer and subscription data is stored locally in `data.json`.

A `data.example.json` template is included in the repository so new users can initialize the project without exposing local data or generated checkout links.

---

# How to Run

Clone the repository.

Install the required dependencies.

```bash
pip install -r requirements.txt
```

Create a local environment file.

```bash
cp .env.example .env
```

Update `.env` with your Nomba Sandbox credentials.

Run the CLI.

```bash
python recurpay.py
```

Open `dashboard.html` in any web browser to view the dashboard.

---

# Notes

* Designed to run on standard Python environments and Termux.
* Uses only lightweight dependencies, including `requests` and `rich`.
* Includes automatic mock fallback mode for offline development and API failures.
* Built for the DevCareer x Nomba Hackathon 2026.



Built for the DevCareer x Nomba Hackathon 2026.
