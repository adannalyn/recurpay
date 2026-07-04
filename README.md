RecurPay MVP

Subscription Payment Tracker for Nigerian Small Business Owners

RecurPay is a Minimum Viable Product (MVP) built for the DevCareer x Nomba Hackathon 2026. It helps Nigerian small business owners manage recurring payments by assigning customers dedicated Nomba virtual accounts, tracking subscription due dates, generating checkout links, and reconciling payments using each customer's "accountRef".

The project combines a command-line interface (CLI) for managing customers and subscriptions with a lightweight HTML dashboard for viewing payment information.

---

Features

- Customer management (create, edit, delete, and list customers)
- Customer virtual account creation using the Nomba Sandbox API
- Recurring subscription management
- Flexible billing frequencies (weekly, monthly, quarterly, yearly, custom intervals, or day-based schedules)
- Automatic due-date tracking
- Checkout link generation
- Payment status management
- Payment reminders for pending and overdue subscriptions
- Transaction reconciliation using customer "accountRef"
- HTML dashboard for viewing customer and payment data
- Local JSON data persistence
- Automatic mock mode when the Nomba Sandbox API is unavailable

---

Technology Stack

- Python
- Requests
- Rich
- python-dotenv
- HTML / CSS / JavaScript
- Nomba Sandbox API

---

Project Structure

recurpay/
├── recurpay.py
├── nomba_api.py
├── models.py
├── storage.py
├── config.py
├── dashboard.html
├── data.example.json
├── .env.example
├── requirements.txt
└── README.md

---

Nomba API Integration

RecurPay integrates with the Nomba Sandbox API for:

- Authentication
- Customer virtual account creation
- Virtual account listing
- Balance retrieval
- Transaction reconciliation
- Checkout link generation
- Checkout status verification

When the Sandbox API is unavailable or returns authentication errors, the application automatically switches to mock mode so all major features remain demonstrable.

---

Architecture

Nomba Parent Account
        │
        ▼
 Team Sub-account
        │
        ▼
Customer Virtual Accounts
        │
        ▼
Recurring Subscriptions
        │
        ▼
Payment Tracking & Reconciliation

Each customer's RecurPay customer ID is used as the Nomba "accountRef", allowing incoming payments to be matched directly to the correct subscription.

---

HTML Dashboard

The dashboard displays:

- Customers
- Assigned virtual accounts
- Upcoming payments
- Overdue payments
- Payment history

The dashboard reads data from "data.json", which is updated by the CLI application.

---

Environment Variables

Copy the example configuration before running the application.

cp .env.example .env

Configure the following variables:

- "NOMBA_ACCOUNT_ID"
- "NOMBA_SUB_ACCOUNT_ID"
- "NOMBA_CLIENT_ID"
- "NOMBA_CLIENT_SECRET"
- "NOMBA_BASE_URL"
- "NOMBA_CALLBACK_URL"
- "DATA_FILE"
- "CURRENCY"
- "DEBUG"

The ".env" file contains local credentials and should not be committed to version control.

---

Data Storage

Runtime customer and subscription data is stored in "data.json".

A "data.example.json" template is included in the repository. On first launch, the application initializes "data.json" from this template if it does not already exist.

---

Installation

Clone the repository.

Install the project dependencies.

pip install -r requirements.txt

Create your environment file.

cp .env.example .env

Update ".env" with your Nomba Sandbox credentials.

Run the application.

python recurpay.py

Open "dashboard.html" in a browser to view the dashboard.

---

Notes

- Designed to run on desktop Python environments and Termux.
- Uses lightweight dependencies for easy setup.
- Includes automatic fallback mode for API failures.
- Built for the DevCareer x Nomba Hackathon 2026.
