import requests
from config import NOMBA_ACCOUNT_ID, NOMBA_CLIENT_ID, NOMBA_CLIENT_SECRET, NOMBA_BASE_URL
from datetime import date
from rich.console import Console
from rich.table import Table

console = Console()

def get_access_token():
    import subprocess
    import json

    cmd = [
        "curl", "--request", "POST",
        "--url", f"{NOMBA_BASE_URL}/auth/token/issue",
        "--header", "Content-Type: application/json",
        "--header", f"accountId: {NOMBA_ACCOUNT_ID}",
        "--data", json.dumps({
            "grant_type": "client_credentials",
            "client_id": NOMBA_CLIENT_ID,
            "client_secret": NOMBA_CLIENT_SECRET
        })
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        if data.get("code") == "00":
            console.print("[green]Nomba authentication successful.[/green]")
            return data["data"]["access_token"]
        else:
            console.print(f"[red]Auth failed: {data}[/red]")
            return None
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return None

customers = []

def add_customer(name, amount, due_date):
    customers.append({
        "name": name,
        "amount": amount,
        "amount_kobo": amount * 100,
        "due_date": due_date,
        "paid": False
    })

def mark_paid(name):
    for c in customers:
        if c["name"].lower() == name.lower():
            c["paid"] = True
            console.print(f"[green]{name} marked as paid.[/green]")
            return
    console.print(f"[red]Customer {name} not found.[/red]")

def show_customers():
    today = date.today()
    table = Table(title="RecurPay - Subscription Tracker")
    table.add_column("Name")
    table.add_column("Amount (NGN)")
    table.add_column("Due Date")
    table.add_column("Status")

    for c in customers:
        due = date.fromisoformat(c["due_date"])
        if c["paid"]:
            status = "[green]✅ Paid[/green]"
        elif due < today:
            status = "[red]⚠️ Overdue[/red]"
        else:
            status = "[yellow]⏳ Pending[/yellow]"
        table.add_row(c["name"], str(c["amount"]), c["due_date"], status)

    console.print(table)

def menu():
    while True:
        console.print("\n[bold]RecurPay Menu[/bold]")
        console.print("1. Add customer")
        console.print("2. View all customers")
        console.print("3. Mark customer as paid")
        console.print("4. Exit")

        choice = input("Choose an option: ")

        if choice == "1":
            name = input("Customer name: ")
            amount = input("Amount (NGN): ")
            due_date = input("Due date (YYYY-MM-DD): ")
            try:
                date.fromisoformat(due_date)
                add_customer(name, int(amount), due_date)
                console.print(f"[green]{name} added.[/green]")
            except ValueError as e:
                if "invalid literal" in str(e):
                    console.print("[red]Invalid amount. Enter numbers only e.g. 5000[/red]")
                else:
                    console.print("[red]Invalid date format. Use YYYY-MM-DD e.g. 2026-07-01[/red]")
        elif choice == "2":
            show_customers()
        elif choice == "3":
            name = input("Customer name: ")
            mark_paid(name)
        elif choice == "4":
            console.print("[yellow]Goodbye.[/yellow]")
            break
        else:
            console.print("[red]Invalid option.[/red]")

token = get_access_token()

menu()
