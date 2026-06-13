import time
import requests
import win32print
import json
import os
from datetime import datetime

BACKEND_URL = "https://restaurant-ai-backend-production-4a7f.up.railway.app"
PRINTER_NAME = "EPSON TM-m30II Receipt"
RESTAURANT_NAME = "Diana's Mexican Grill"

printed_orders = set()
PRINTED_ORDERS_FILE = "printed_orders.json"

try:
    with open(PRINTED_ORDERS_FILE, "r") as f:
        printed_orders = set(json.load(f))
except:
    printed_orders = set()

def print_ticket(order):
    items = order["items"].replace(", ", "\n- ")

    ticket = f"""
{RESTAURANT_NAME}

*** NEW PICKUP ORDER ***

ORDER #{order['id']}
Time: {datetime.now().strftime("%I:%M %p")}

Customer: {order['customer_name']}
Phone: {order['phone_number']}

-----------------------
ITEMS:
- {items}

NOTES:
{order['notes'] or "None"}



"""

    printer = win32print.OpenPrinter(PRINTER_NAME)

    try:
        win32print.StartDocPrinter(printer, 1, ("Kitchen Ticket", None, "RAW"))
        win32print.StartPagePrinter(printer)

        win32print.WritePrinter(printer, b"\x1b\x21\x30")
        win32print.WritePrinter(printer, ticket.encode("utf-8"))
        win32print.WritePrinter(printer, b"\x1b\x21\x00")
        win32print.WritePrinter(printer, b"\x1d\x56\x00")

        win32print.EndPagePrinter(printer)
        win32print.EndDocPrinter(printer)

    finally:
        win32print.ClosePrinter(printer) 

print("Printer Agent Started")

while True:
    try:
        response = requests.get(f"{BACKEND_URL}/orders")
        orders = response.json()

        for order in orders:
            if order["status"] == "NEW" and order["id"] not in printed_orders:
                print(f"Printing order #{order['id']}")
                print_ticket(order)

                printed_orders.add(order["id"])

                with open(PRINTED_ORDERS_FILE, "w") as f:
                    json.dump(list(printed_orders), f)

    except Exception as e:
        print("Printer error:", e)

    time.sleep(5)