import datetime
import uuid
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text

from config import CURRENCY
from models import Customer, Subscription
from storage import JSONStorage
from nomba_api import NombaAPI

console = Console()
storage = JSONStorage()
nomba_api = NombaAPI()

def display_customer_table(customers):
    table = Table(title="Customer List")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="magenta")
    table.add_column("Email", style="green")

    for customer in customers:
        table.add_row(customer.customer_id[:8] + "...", customer.name, customer.email)
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
    customer_id = Prompt.ask("Enter customer ID to edit")
    customer = storage.get_customer(customer_id)
    if not customer:
        console.print("[red]Customer not found.[/red]")
        return
    console.print(f"[bold blue]Editing Customer: {customer.name} ({customer.email})[/bold blue]")
    new_name = Prompt.ask(f"Enter new name (current: {customer.name})", default=customer.name)
    new_email = Prompt.ask(f"Enter new email (current: {customer.email})", default=customer.email)
    if storage.update_customer(customer_id, new_name, new_email):
        console.print("[green]Customer updated successfully.[/green]")
    else:
        console.print("[red]Failed to update customer.[/red]")

def delete_customer():
    customer_id = Prompt.ask("Enter customer ID to delete")
    if Confirm.ask(f"[red]Are you sure you want to delete customer {customer_id} and all their subscriptions?[/red]"):
        if storage.delete_customer(customer_id):
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
    customer_id = Prompt.ask("Enter customer ID for this subscription")
    customer = storage.get_customer(customer_id)
    if not customer:
        console.print("[red]Customer not found.[/red]")
        return

    description = Prompt.ask("Enter subscription description")
    amount = float(Prompt.ask("Enter amount"))
    frequency = Prompt.ask("Enter frequency (weekly, monthly, custom:X_days)")
    start_date_str = Prompt.ask("Enter start date (YYYY-MM-DD)", default=datetime.date.today().isoformat())
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")

    subscription = Subscription(customer_id, amount, frequency, start_date, description)
    storage.add_subscription(subscription)
    console.print(f"[green]Subscription '{description}' added for {customer.name}.[/green]")

def list_subscriptions():
    subscriptions = storage.list_subscriptions()
    if not subscriptions:
        console.print("[yellow]No subscriptions found.[/yellow]")
        return
    display_subscription_table(subscriptions)

def update_subscription_status():
    subscription_id = Prompt.ask("Enter subscription ID to update status")
    subscription = storage.get_subscription(subscription_id)
    if not subscription:
        console.print("[red]Subscription not found.[/red]")
        return

    console.print(f"[bold blue]Updating Subscription: {subscription.description} (Current Status: {subscription.status})[/bold blue]")
    new_status = Prompt.ask("Enter new status (pending, paid, overdue)", default=subscription.status)
    if new_status not in ["pending", "paid", "overdue"]:
        console.print("[red]Invalid status. Please choose from 'pending', 'paid', 'overdue'.[/red]")
        return

    if new_status == "paid":
        subscription.last_payment_date = datetime.datetime.now()
        subscription.update_next_due_date()

    if storage.update_subscription(subscription_id, status=new_status, last_payment_date=subscription.last_payment_date, next_due_date=subscription.next_due_date):
        console.print("[green]Subscription status updated successfully.[/green]")
    else:
        console.print("[red]Failed to update subscription status.[/red]")

def generate_payment_link():
    subscription_id = Prompt.ask("Enter subscription ID to generate payment link")
    subscription = storage.get_subscription(subscription_id)
    if not subscription:
        console.print("[red]Subscription not found.[/red]")
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
        storage.update_subscription(subscription_id, checkout_link=checkout_link)
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
        console.print("4. Generate Payment Link")
        console.print("5. Exit")

        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3", "4", "5"])

        if choice == "1":
            customer_menu()
        elif choice == "2":
            subscription_menu()
        elif choice == "3":
            list_reminders()
        elif choice == "4":
            generate_payment_link()
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
        console.print("4. Back to Main Menu")

        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3", "4"])

        if choice == "1":
            add_subscription()
        elif choice == "2":
            list_subscriptions()
        elif choice == "3":
            update_subscription_status()
        elif choice == "4":
            break

if __name__ == "__main__":
    main_menu()
