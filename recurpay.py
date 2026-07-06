import datetime
import uuid
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text

from config import CURRENCY
from models import Customer, Subscription
from storage import JSONStorage
from nomba_api import NombaAPI, frequency_to_nomba_enum, generate_numeric_reference

console = Console()
storage = JSONStorage()
nomba_api = NombaAPI()

def display_customer_table(customers):
    table = Table(title="Customer List")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="magenta")
    table.add_column("Email", style="green")
    table.add_column("Virtual Account", style="yellow")

    for customer in customers:
        virtual_account = customer.virtual_account or {}
        account_number = virtual_account.get("bankAccountNumber")
        bank_name = virtual_account.get("bankName")
        account_label = f"{bank_name} {account_number}" if account_number and bank_name else "Not created"
        table.add_row(customer.customer_id[:8] + "...", customer.name, customer.email, account_label)
    console.print(table)

def display_subscription_table(subscriptions, show_customer_name=True):
    table = Table(title="Subscription List")
    table.add_column("ID", style="cyan", no_wrap=True)
    if show_customer_name:
        table.add_column("Customer", style="magenta")
    table.add_column("Description", style="green")
    table.add_column("Amount", style="yellow")
    table.add_column("Frequency", style="blue")
    table.add_column("Next Due", style="red")
    table.add_column("Status", style="bold white")
    table.add_column("Checkout Link", style="dim")

    for sub in subscriptions:
        customer = storage.get_customer(sub.customer_id)
        customer_name = customer.name if customer else "Unknown"
        status_text = Text(sub.status.capitalize())
        if sub.status == "overdue":
            status_text.stylize("bold red")
        elif sub.status == "paid":
            status_text.stylize("bold green")
        elif sub.status == "pending":
            status_text.stylize("bold yellow")

        row = [
            sub.subscription_id[:8] + "...",
            customer_name if show_customer_name else None,
            sub.description,
            f"{sub.amount:.2f} {CURRENCY}",
            sub.frequency,
            sub.next_due_date.strftime("%Y-%m-%d"),
            status_text,
            sub.checkout_link or "N/A"
        ]
        if not show_customer_name:
            row.pop(1) # Remove customer name if not needed
        table.add_row(*row)
    console.print(table)

def resolve_customer(query):
    """Resolve a customer by full ID, ID prefix, name, or email.
    Prints a helpful message and returns None on zero or multiple
    matches (showing the candidates so the user can narrow down)."""
    matches = storage.find_customers(query)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        console.print(f"[red]No customer found matching '{query}'.[/red]")
        return None
    console.print(f"[yellow]Multiple customers match '{query}':[/yellow]")
    display_customer_table(matches)
    console.print("[yellow]Try again with a more specific name, email, or the ID prefix shown above.[/yellow]")
    return None

def resolve_subscription(query):
    """Resolve a subscription by full ID, ID prefix, description text,
    or the associated customer's name. Prints a helpful message and
    returns None on zero or multiple matches."""
    matches = storage.find_subscriptions(query)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        console.print(f"[red]No subscription found matching '{query}'.[/red]")
        return None
    console.print(f"[yellow]Multiple subscriptions match '{query}':[/yellow]")
    display_subscription_table(matches)
    console.print("[yellow]Try again with a more specific description, customer name, or the ID prefix shown above.[/yellow]")
    return None

def add_customer():
    console.print("[bold blue]Add New Customer[/bold blue]")
    name = Prompt.ask("Enter customer name")
    email = Prompt.ask("Enter customer email")
    customer = Customer(name, email)
    storage.add_customer(customer)
    console.print(f"[green]Customer '{name}' added with ID {customer.customer_id}[/green]")

def list_customers():
    customers = storage.list_customers()
    if not customers:
        console.print("[yellow]No customers found.[/yellow]")
        return
    display_customer_table(customers)

def edit_customer():
    query = Prompt.ask("Enter customer name, email, or ID to edit")
    customer = resolve_customer(query)
    if not customer:
        return
    console.print(f"[bold blue]Editing Customer: {customer.name} ({customer.email})[/bold blue]")
    new_name = Prompt.ask(f"Enter new name (current: {customer.name})", default=customer.name)
    new_email = Prompt.ask(f"Enter new email (current: {customer.email})", default=customer.email)
    if storage.update_customer(customer.customer_id, new_name, new_email):
        console.print("[green]Customer updated successfully.[/green]")
    else:
        console.print("[red]Failed to update customer.[/red]")

def delete_customer():
    query = Prompt.ask("Enter customer name, email, or ID to delete")
    customer = resolve_customer(query)
    if not customer:
        return
    if Confirm.ask(f"[red]Are you sure you want to delete {customer.name} and all their subscriptions?[/red]"):
        if storage.delete_customer(customer.customer_id):
            console.print("[green]Customer and associated subscriptions deleted.[/green]")
        else:
            console.print("[red]Customer not found.[/red]")

def add_subscription():
    console.print("[bold blue]Add New Subscription[/bold blue]")
    customers = storage.list_customers()
    if not customers:
        console.print("[red]No customers available. Please add a customer first.[/red]")
        return
    display_customer_table(customers)
    query = Prompt.ask("Enter customer name, email, or ID for this subscription")
    customer = resolve_customer(query)
    if not customer:
        return

    description = Prompt.ask("Enter subscription description")
    amount = float(Prompt.ask("Enter amount"))
    frequency = Prompt.ask("Enter frequency (weekly, monthly, quarterly, 90 days, custom:7)")
    start_date_str = Prompt.ask("Enter start date (YYYY-MM-DD)", default=datetime.date.today().isoformat())
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")

    try:
        subscription = Subscription(customer.customer_id, amount, frequency, start_date, description)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        return

    storage.add_subscription(subscription)
    console.print(f"[green]Subscription '{description}' added for {customer.name}.[/green]")

def list_subscriptions():
    subscriptions = storage.list_subscriptions()
    if not subscriptions:
        console.print("[yellow]No subscriptions found.[/yellow]")
        return
    display_subscription_table(subscriptions)

def create_customer_virtual_account():
    console.print("[bold blue]Create Customer Virtual Account[/bold blue]")
    customers = storage.list_customers()
    if not customers:
        console.print("[red]No customers available. Please add a customer first.[/red]")
        return

    display_customer_table(customers)
    query = Prompt.ask("Enter customer name, email, or ID for the virtual account")
    customer = resolve_customer(query)
    if not customer:
        return

    existing_account = customer.virtual_account or {}
    if existing_account.get("bankAccountNumber"):
        replace = Confirm.ask(
            f"[yellow]{customer.name} already has a virtual account. Replace it?[/yellow]",
            default=False
        )
        if not replace:
            return

    virtual_account = nomba_api.create_virtual_account_for_sub_account(
        account_ref=customer.customer_id,
        account_name=customer.name
    )

    if not virtual_account:
        console.print("[red]Failed to create virtual account.[/red]")
        return

    storage.update_customer(customer.customer_id, virtual_account=virtual_account)
    bank_name = virtual_account.get("bankName", "Unknown bank")
    account_number = virtual_account.get("bankAccountNumber", "N/A")
    account_name = virtual_account.get("bankAccountName", virtual_account.get("accountName", customer.name))
    mock_note = " [yellow](mock)[/yellow]" if virtual_account.get("mock") else ""

    console.print(f"[green]Virtual account created for {customer.name}.{mock_note}[/green]")
    console.print(f"Bank: [bold]{bank_name}[/bold]")
    console.print(f"Account Number: [bold]{account_number}[/bold]")
    console.print(f"Account Name: [bold]{account_name}[/bold]")
    console.print(f"Account Ref: [bold]{virtual_account.get('accountRef', customer.customer_id)}[/bold]")

def expire_customer_virtual_account():
    console.print("[bold blue]Expire / Delete Customer Virtual Account[/bold blue]")
    customers = [c for c in storage.list_customers() if (c.virtual_account or {}).get("bankAccountNumber")]
    if not customers:
        console.print("[yellow]No customers currently have a virtual account.[/yellow]")
        return

    display_customer_table(customers)
    query = Prompt.ask("Enter customer name, email, or ID whose virtual account should be removed")
    customer = resolve_customer(query)
    if not customer:
        return

    virtual_account = customer.virtual_account or {}
    account_number = virtual_account.get("bankAccountNumber")
    if not account_number:
        console.print(f"[yellow]{customer.name} does not have a virtual account to remove.[/yellow]")
        return

    if not Confirm.ask(
        f"[red]Remove the virtual account for {customer.name} ({account_number})? "
        f"This cannot be undone.[/red]",
        default=False
    ):
        return

    identifier = virtual_account.get("accountRef", customer.customer_id)
    was_mock = nomba_api.mock_mode
    result = nomba_api.expire_virtual_account(identifier)

    # The virtual account slot lives on the local customer record regardless
    # of whether Nomba's servers confirm the expiry, so clear it either way -
    # this mirrors how creation already treats local storage as authoritative
    # for mock-mode accounts.
    storage.update_customer(customer.customer_id, virtual_account={})

    if was_mock or nomba_api.mock_mode or (isinstance(result, dict) and result.get("mock")):
        console.print(
            f"[green]Removed the locally stored virtual account for {customer.name}.[/green] "
            f"[dim](Nomba API is in mock mode, so nothing was expired on Nomba's servers - "
            f"only the local record was cleared.)[/dim]"
        )
    else:
        console.print(f"[green]Virtual account for {customer.name} expired via the Nomba API and removed locally.[/green]")

def setup_direct_debit_mandate():
    console.print("[bold blue]Set Up Direct Debit Mandate[/bold blue]")
    console.print(
        "[dim]This authorizes RecurPay to auto-charge a customer's bank account on a "
        "fixed schedule, instead of waiting for them to click a payment link. The "
        "customer must still complete a one-time bank authorization step before it's active.[/dim]"
    )
    query = Prompt.ask("Enter customer name, email, or ID to set up a mandate for")
    customer = resolve_customer(query)
    if not customer:
        return

    existing = customer.direct_debit_mandate or {}
    if existing.get("mandateId"):
        if not Confirm.ask(
            f"[yellow]{customer.name} already has a mandate on file. Replace it?[/yellow]",
            default=False
        ):
            return

    account_number = Prompt.ask("Customer's bank account number")
    bank_code = Prompt.ask("Customer's bank code (e.g. from Nomba's bank list)")
    phone_number = Prompt.ask("Customer's phone number")
    address = Prompt.ask("Customer's address", default="")
    amount = float(Prompt.ask("Amount to auto-charge per cycle"))
    frequency = Prompt.ask("Frequency (weekly, biweekly, monthly, quarterly, or yearly)")

    try:
        nomba_frequency = frequency_to_nomba_enum(frequency)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        return

    start_date = datetime.datetime.now()
    duration_months_str = Prompt.ask("How many months should this mandate run for?", default="12")
    try:
        duration_months = int(duration_months_str)
    except ValueError:
        console.print("[red]Duration must be a whole number of months.[/red]")
        return
    end_date = start_date + datetime.timedelta(days=30 * duration_months)

    merchant_reference = generate_numeric_reference(customer.customer_id)
    mandate = nomba_api.create_direct_debit_mandate(
        customer_account_number=account_number,
        bank_code=bank_code,
        customer_name=customer.name,
        customer_account_name=customer.name,
        customer_email=customer.email,
        customer_phone_number=phone_number,
        amount=amount,
        frequency=nomba_frequency,
        start_date=start_date.strftime("%Y-%m-%dT%H:%M"),
        end_date=end_date.strftime("%Y-%m-%dT%H:%M"),
        merchant_reference=merchant_reference,
        customer_address=address
    )

    if not mandate:
        console.print("[red]Failed to create mandate.[/red]")
        return

    storage.update_customer(customer.customer_id, direct_debit_mandate=mandate)

    mock_note = " [yellow](mock)[/yellow]" if mandate.get("mock") else ""
    console.print(f"[green]Mandate created for {customer.name}.{mock_note}[/green]")
    console.print(f"Mandate ID: [bold]{mandate.get('mandateId')}[/bold]")
    if mandate.get("description"):
        console.print(f"[yellow]Next step - relay this to the customer:[/yellow]\n{mandate['description']}")

def charge_subscription_via_mandate():
    query = Prompt.ask("Enter subscription description, customer name, or ID to charge")
    subscription = resolve_subscription(query)
    if not subscription:
        return

    customer = storage.get_customer(subscription.customer_id)
    if not customer:
        console.print("[red]Associated customer not found.[/red]")
        return

    mandate = customer.direct_debit_mandate or {}
    mandate_id = mandate.get("mandateId")
    if not mandate_id:
        console.print(f"[red]{customer.name} has no direct debit mandate set up yet.[/red]")
        return

    if mandate.get("status") not in (None, "ACTIVE", "active"):
        console.print(
            f"[yellow]This mandate's status is '{mandate.get('status')}', not confirmed active. "
            f"The charge may fail if the customer hasn't completed authorization yet.[/yellow]"
        )

    reference = generate_numeric_reference(subscription.subscription_id)
    result = nomba_api.debit_mandate(mandate_id, subscription.amount, reference, subscription.description)

    if not result:
        console.print("[red]Failed to charge mandate.[/red]")
        return

    is_mock = nomba_api.mock_mode or (isinstance(result, dict) and result.get("mock"))
    status = str(result.get("status", "")).lower()

    if status in ("successful", "success"):
        subscription.last_payment_date = datetime.datetime.now()
        subscription.update_next_due_date()
        storage.update_subscription(
            subscription.subscription_id,
            status="paid",
            last_payment_date=subscription.last_payment_date,
            next_due_date=subscription.next_due_date
        )
        mock_note = " [yellow](mock - not a real charge)[/yellow]" if is_mock else ""
        console.print(f"[green]Charged {customer.name} {subscription.amount:.2f} {CURRENCY} and marked paid.{mock_note}[/green]")
    else:
        console.print(f"[red]Charge did not succeed. Status: {result.get('status', 'unknown')}[/red]")

def _records_from_payload(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("transactions", "virtualAccounts", "virtual_accounts", "accounts", "items", "records", "results", "content", "data"):
        value = payload.get(key)
        records = _records_from_payload(value)
        if records:
            return records
    return []

def _nested_value(data, *keys):
    if not isinstance(data, dict):
        return None

    for key in keys:
        if key in data:
            return data[key]

    for value in data.values():
        found = _nested_value(value, *keys)
        if found is not None:
            return found
    return None

def _customer_from_transaction(transaction):
    account_ref = _nested_value(transaction, "accountRef", "accountReference", "account_ref")
    if account_ref:
        customer = storage.get_customer(account_ref)
        if customer:
            return customer, account_ref

    account_number = _nested_value(
        transaction,
        "bankAccountNumber",
        "accountNumber",
        "account_number",
        "destinationAccountNumber"
    )
    if account_number:
        for customer in storage.list_customers():
            virtual_account = customer.virtual_account or {}
            if str(virtual_account.get("bankAccountNumber")) == str(account_number):
                return customer, virtual_account.get("accountRef", customer.customer_id)

    return None, account_ref or "N/A"

def _local_virtual_accounts():
    """Build a virtual-account list from customers' locally stored
    virtual_account data. Used as a mock-mode fallback since the Nomba
    mock list endpoint has no knowledge of accounts we generated and
    saved locally (create and list are separate, unconnected mock paths)."""
    accounts = []
    for customer in storage.list_customers():
        virtual_account = customer.virtual_account or {}
        if virtual_account.get("bankAccountNumber"):
            accounts.append(virtual_account)
    return accounts

def list_nomba_virtual_accounts():
    console.print("[bold blue]Nomba Virtual Accounts[/bold blue]")
    payload = nomba_api.list_virtual_accounts()
    accounts = _records_from_payload(payload)
    showing_local_fallback = False

    if not accounts and nomba_api.mock_mode:
        accounts = _local_virtual_accounts()
        showing_local_fallback = bool(accounts)

    if not accounts:
        console.print("[yellow]No virtual accounts returned yet.[/yellow]")
        return

    if showing_local_fallback:
        console.print(
            "[dim]Nomba API is in mock mode with no server-side record of created accounts. "
            "Showing virtual accounts stored locally instead.[/dim]"
        )

    table = Table(title="Virtual Accounts")
    table.add_column("Account Ref", style="cyan")
    table.add_column("Account Name", style="magenta")
    table.add_column("Bank", style="green")
    table.add_column("Account Number", style="yellow")
    table.add_column("Status", style="white")

    for account in accounts:
        table.add_row(
            str(_nested_value(account, "accountRef", "accountReference", "account_ref") or "N/A"),
            str(_nested_value(account, "accountName", "bankAccountName", "account_name") or "N/A"),
            str(_nested_value(account, "bankName", "bank_name") or "N/A"),
            str(_nested_value(account, "bankAccountNumber", "accountNumber", "account_number") or "N/A"),
            "Expired" if _nested_value(account, "expired") else "Active"
        )
    console.print(table)

def view_nomba_balance():
    console.print("[bold blue]Nomba Sub-account Balance[/bold blue]")
    balance = nomba_api.get_sub_account_balance()

    if not isinstance(balance, dict):
        console.print(f"[yellow]Balance response:[/yellow] {balance}")
        return

    table = Table(title="Sub-account Balance")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    for key, value in balance.items():
        if isinstance(value, (dict, list)):
            continue
        table.add_row(str(key), str(value))
    console.print(table)

def reconcile_nomba_transactions():
    console.print("[bold blue]Reconcile Nomba Transactions[/bold blue]")
    payload = nomba_api.list_sub_account_transactions()
    transactions = _records_from_payload(payload)

    if not transactions:
        console.print("[yellow]No transactions returned yet. In production, webhooks should update payments as inflows arrive.[/yellow]")
        return

    table = Table(title="Transaction Reconciliation")
    table.add_column("Customer", style="magenta")
    table.add_column("Account Ref", style="cyan")
    table.add_column("Amount", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Session ID", style="blue")
    table.add_column("Date", style="white")

    for transaction in transactions:
        customer, account_ref = _customer_from_transaction(transaction)
        amount = _nested_value(transaction, "amount", "transactionAmount", "paidAmount")
        status = _nested_value(transaction, "status", "transactionStatus", "paymentStatus")
        session_id = _nested_value(transaction, "sessionId", "sessionID", "session_id")
        date = _nested_value(transaction, "createdAt", "created_at", "paymentDate", "transactionDate")
        table.add_row(
            customer.name if customer else "Unmatched",
            str(account_ref),
            str(amount or "N/A"),
            str(status or "N/A"),
            str(session_id or "N/A"),
            str(date or "N/A")
        )
    console.print(table)

def update_subscription_status():
    query = Prompt.ask("Enter subscription description, customer name, or ID to update")
    subscription = resolve_subscription(query)
    if not subscription:
        return

    console.print(f"[bold blue]Updating Subscription: {subscription.description} (Current Status: {subscription.status})[/bold blue]")
    new_status = Prompt.ask("Enter new status (pending, paid, overdue)", default=subscription.status)
    if new_status not in ["pending", "paid", "overdue"]:
        console.print("[red]Invalid status. Please choose from 'pending', 'paid', 'overdue'.[/red]")
        return

    if new_status == "paid":
        subscription.last_payment_date = datetime.datetime.now()
        subscription.update_next_due_date()

    if storage.update_subscription(subscription.subscription_id, status=new_status, last_payment_date=subscription.last_payment_date, next_due_date=subscription.next_due_date):
        console.print("[green]Subscription status updated successfully.[/green]")
    else:
        console.print("[red]Failed to update subscription status.[/red]")

def delete_subscription_flow():
    query = Prompt.ask("Enter subscription description, customer name, or ID to delete")
    subscription = resolve_subscription(query)
    if not subscription:
        return

    customer = storage.get_customer(subscription.customer_id)
    customer_name = customer.name if customer else "Unknown customer"

    if not Confirm.ask(
        f"[red]Delete subscription '{subscription.description}' for {customer_name} "
        f"({subscription.amount:.2f} {CURRENCY}, {subscription.frequency})? This cannot be undone.[/red]",
        default=False
    ):
        return

    if storage.delete_subscription(subscription.subscription_id):
        console.print("[green]Subscription deleted.[/green]")
    else:
        console.print("[red]Failed to delete subscription.[/red]")

def generate_payment_link():
    query = Prompt.ask("Enter subscription description, customer name, or ID to generate a payment link for")
    subscription = resolve_subscription(query)
    if not subscription:
        return

    customer = storage.get_customer(subscription.customer_id)
    if not customer:
        console.print("[red]Associated customer not found. Cannot generate link.[/red]")
        return

    order_ref = f"RECURPAY-{subscription.subscription_id}"
    checkout_link = nomba_api.generate_checkout_link(
        subscription.amount,
        customer.email,
        order_ref,
        subscription.description
    )

    if checkout_link:
        storage.update_subscription(subscription.subscription_id, checkout_link=checkout_link)
        console.print(f"[green]Generated checkout link for {subscription.description}:[/green] {checkout_link}")
    else:
        console.print("[red]Failed to generate checkout link.[/red]")

def list_reminders():
    console.print("[bold blue]Payment Reminders (Pending/Overdue Subscriptions)[/bold blue]")
    today = datetime.date.today()
    reminders = []
    for sub in storage.list_subscriptions():
        if sub.next_due_date.date() <= today and sub.status != "paid":
            reminders.append(sub)
            # Automatically mark as overdue if due date passed and not paid
            if sub.next_due_date.date() < today and sub.status == "pending":
                storage.update_subscription(sub.subscription_id, status="overdue")
                sub.status = "overdue" # Update in current object for display

    if not reminders:
        console.print("[green]No pending or overdue payments. All clear![/green]")
        return

    display_subscription_table(reminders)

def main_menu():
    while True:
        console.print("\n[bold underline]RecurPay CLI Menu[/bold underline]")
        console.print("1. Manage Customers")
        console.print("2. Manage Subscriptions")
        console.print("3. List Payment Reminders")
        console.print("4. Nomba Tools")
        console.print("5. Exit")

        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3", "4", "5"])

        if choice == "1":
            customer_menu()
        elif choice == "2":
            subscription_menu()
        elif choice == "3":
            list_reminders()
        elif choice == "4":
            nomba_menu()
        elif choice == "5":
            console.print("[bold green]Exiting RecurPay. Goodbye![/bold green]")
            break

def customer_menu():
    while True:
        console.print("\n[bold underline]Customer Management[/bold underline]")
        console.print("1. Add Customer")
        console.print("2. List Customers")
        console.print("3. Edit Customer")
        console.print("4. Delete Customer")
        console.print("5. Back to Main Menu")

        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3", "4", "5"])

        if choice == "1":
            add_customer()
        elif choice == "2":
            list_customers()
        elif choice == "3":
            edit_customer()
        elif choice == "4":
            delete_customer()
        elif choice == "5":
            break

def subscription_menu():
    while True:
        console.print("\n[bold underline]Subscription Management[/bold underline]")
        console.print("1. Add Subscription")
        console.print("2. List Subscriptions")
        console.print("3. Update Subscription Status")
        console.print("4. Delete Subscription")
        console.print("5. Charge Subscription (Direct Debit)")
        console.print("6. Back to Main Menu")

        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3", "4", "5", "6"])

        if choice == "1":
            add_subscription()
        elif choice == "2":
            list_subscriptions()
        elif choice == "3":
            update_subscription_status()
        elif choice == "4":
            delete_subscription_flow()
        elif choice == "5":
            charge_subscription_via_mandate()
        elif choice == "6":
            break

def nomba_menu():
    while True:
        console.print("\n[bold underline]Nomba Tools[/bold underline]")
        console.print("1. Create Customer Virtual Account")
        console.print("2. List Virtual Accounts")
        console.print("3. View Sub-account Balance")
        console.print("4. Reconcile Transactions")
        console.print("5. Generate Checkout Link")
        console.print("6. Expire/Delete Customer Virtual Account")
        console.print("7. Set Up Direct Debit Mandate")
        console.print("8. Back to Main Menu")

        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3", "4", "5", "6", "7", "8"])

        if choice == "1":
            create_customer_virtual_account()
        elif choice == "2":
            list_nomba_virtual_accounts()
        elif choice == "3":
            view_nomba_balance()
        elif choice == "4":
            reconcile_nomba_transactions()
        elif choice == "5":
            generate_payment_link()
        elif choice == "6":
            expire_customer_virtual_account()
        elif choice == "7":
            setup_direct_debit_mandate()
        elif choice == "8":
            break

if __name__ == "__main__":
    main_menu()