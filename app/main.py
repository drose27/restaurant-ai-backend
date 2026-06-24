from importlib.resources import files
from aiohttp_retry import List
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from twilio.rest import Client
import os
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

app = FastAPI()

app.mount("/uploaded_menus", StaticFiles(directory="uploaded_menus"), name="uploaded_menus")

def log_event(event_type, message):
    db = SessionLocal()

    log = LogDB(
        event_type=event_type,
        message=message,
        created_at=str(datetime.now())
    )

    db.add(log)
    db.commit()
    db.close()

class Order(BaseModel):
    customer_name: str
    phone_number: str
    items: list[str]
    notes: str = ""
    subtotal: float
    tax_rate: float
    total: float

class OrderDB(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String)
    phone_number = Column(String)
    items = Column(String)
    notes = Column(String)
    subtotal = Column(Float)
    tax_rate = Column(Float)
    total = Column(Float)
    status = Column(String, default="NEW")
    created_at = Column(String)

class RestaurantSettings(Base):
    __tablename__ = "restaurant_settings"

    id = Column(Integer, primary_key=True, index=True)

    restaurant_name = Column(String)
    phone_number = Column(String)
    address = Column(String)

    tax_rate = Column(Float, default=0.0)

    pickup_message = Column(
        String,
        default="Your order is ready for pickup!"
    )
class RestaurantSettingsForm(BaseModel):
    restaurant_name: str
    phone_number: str
    address: str
    tax_rate: float
    pickup_message: str

class LogDB(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String)
    message = Column(String)
    created_at = Column(String)

Base.metadata.create_all(bind=engine)

@app.get("/")
def home():
    return {"message": "Restaurant AI backend is working!"}

@app.post("/orders")
def create_order(order: Order):

    db_order = OrderDB(
        customer_name=order.customer_name,
        phone_number=order.phone_number,
        items=", ".join(order.items),
        notes=order.notes,
        subtotal=order.subtotal,
        tax_rate=order.tax_rate,
        total=order.total,
        status="NEEDS_CALLBACK" if "Callback request" in order.items else "NEW",
        created_at=str(datetime.now())
    )

    db = SessionLocal()

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    log_event(
    "NEW_ORDER",
    f"{order.customer_name} - ${order.total}"
)
    
    db.close()

    return {
        "status": "order saved to PostgreSQL",
        "order_id": db_order.id
    }

@app.get("/api/orders")
def get_orders():
    db = SessionLocal()
    orders = db.query(OrderDB).order_by(OrderDB.id.desc()).all()
    db.close()
    return orders

@app.get("/logs", response_class=HTMLResponse)
def get_logs():
    db = SessionLocal()
    logs = db.query(LogDB).order_by(LogDB.id.desc()).all()
    db.close()

    html = """
    <html>
    <head>
        <title>System Logs</title>
        <style>
            body { font-family: Arial; padding: 30px; background: #f7f7f7; }
            h1 { color: #222; }
            table { width: 100%; border-collapse: collapse; background: white; }
            th, td { padding: 12px; border-bottom: 1px solid #ddd; text-align: left; }
            th { background: #333; color: white; }
            .event { font-weight: bold; color: green; }
        </style>
    </head>
    <body>
        <h1>System Logs</h1>
        <table>
            <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Message</th>
            </tr>
    """

    for log in logs:
        html += f"""
            <tr>
                <td>{log.created_at}</td>
                <td class="event">{log.event_type}</td>
                <td>{log.message}</td>
            </tr>
        """

    html += """
        </table>
    </body>
    </html>
    """
    return html

@app.post("/settings")
def save_settings(
    restaurant_name: str = Form(...),
    phone_number: str = Form(...),
    address: str = Form(...),
    tax_rate: float = Form(...),
    pickup_message: str = Form(...)
):
    db = SessionLocal()

    settings = db.query(RestaurantSettings).first()

    if not settings:
        settings = RestaurantSettings()

    settings.restaurant_name = restaurant_name
    settings.phone_number = phone_number
    settings.address = address
    settings.tax_rate = tax_rate
    settings.pickup_message = pickup_message

    db.add(settings)
    db.commit()

    db.close()

    return RedirectResponse(
        url="/settings",
        status_code=303
    )

@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    db = SessionLocal()

    settings = db.query(RestaurantSettings).first()

    if not settings:
        settings = RestaurantSettings(
            restaurant_name="Diana's Mexican Grill",
            phone_number="",
            address="",
            tax_rate=0.0,
            pickup_message="Your order is ready for pickup!"
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    db.close()

    html = f"""
    <html>
    <head>
        <title>Restaurant Settings</title>
        <style>
            body {{ font-family: Arial; padding: 30px; background: #f7f7f7; }}
            .box {{ background: white; padding: 25px; border-radius: 12px; max-width: 600px; }}
            input, textarea {{ width: 100%; padding: 10px; margin: 8px 0 18px 0; font-size: 16px; }}
            button {{ padding: 12px 20px; font-size: 16px; cursor: pointer; }}
            a {{ display: inline-block; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <a href="/dashboard">← Back to Dashboard</a>

        <div class="box">
            <h1>Restaurant Settings</h1>

            <form method="post" action="/settings">
                <label>Restaurant Name</label>
                <input name="restaurant_name" value="{settings.restaurant_name}">

                <label>Phone Number</label>
                <input name="phone_number" value="{settings.phone_number}">

                <label>Address</label>
                <input name="address" value="{settings.address}">

                <label>Tax Rate</label>
                <input name="tax_rate" value="{settings.tax_rate}">

                <label>Pickup Message</label>
                <textarea name="pickup_message">{settings.pickup_message}</textarea>

                <button type="submit">Save Settings</button>
            </form>
        </div>
    </body>
    </html>
    """

    return html

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    db = SessionLocal()

    settings = db.query(RestaurantSettings).first()

    restaurant_name = "Restaurant Orders"
    if settings and settings.restaurant_name:
        restaurant_name = settings.restaurant_name

    orders = db.query(OrderDB).order_by(OrderDB.id.desc()).all()

    cutoff = datetime.now() - timedelta(hours=24)

    orders_today = [
        order for order in orders [ :5]
        if getattr(order, "created_at", None)
        and datetime.fromisoformat(str(order.created_at)) >= cutoff
    ]

    orders_today_count = len(orders_today)
    revenue_today = sum(order.total or 0 for order in orders_today)

    waiting_orders = len([order for order in orders_today if order.status == "NEW"])
    preparing_orders = len([order for order in orders_today if order.status == "PREPARING"])
    ready_orders = len([order for order in orders_today if order.status == "READY"])
    callback_orders = len([order for order in orders_today if order.status == "NEEDS_CALLBACK"])

    html = f"""
    <html>
    <head>
    <title>Restaurant Orders</title>
    <style>
            body {{ font-family: Arial; padding: 30px; background: #f7f7f7; }}
h1 {{ color: #222; }}
.order {{
                background: white;
                padding: 20px;
                margin-bottom: 15px;
                border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
.new {{ color: green; font-weight: bold; }}
        </style>
<meta http-equiv="refresh" content="5">
<audio id="ding" preload="auto" src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg"></audio>

<script>
const newestOrder = "{orders[0].id if orders else 0}";
const lastSeen = localStorage.getItem("lastOrderId");

if (!lastSeen) {{
    localStorage.setItem("lastOrderId", newestOrder);
}} else if (newestOrder !== lastSeen) {{
    localStorage.setItem("lastOrderId", newestOrder);
    document.getElementById("ding").play().catch(() => {{}});
}}
</script>
</head>
<body>
    <h1>{restaurant_name}</h1>
<div style="
    background:#1f2937;
    padding:15px;
    border-radius:10px;
    margin-bottom:20px;
">
    <a href="/dashboard" style="color:white;text-decoration:none;margin-right:20px;">
        🏠 Dashboard
    </a>

    <a href="/orders" style="color:white;text-decoration:none;margin-right:20px;">
        📦 Orders
    </a>

    <a href="/menu" style="color:white;text-decoration:none;margin-right:20px;">
        📋 Menu
    </a>

    <a href="/settings" style="color:white;text-decoration:none;">
        ⚙️ Settings
    </a>
</div>

<div class="order">
    <h2>Today's Summary</h2>
    <p><strong>Orders Today:</strong> {orders_today_count}</p>
    <p><strong>Revenue Today:</strong> ${revenue_today:.2f}</p>
    <p><strong>Waiting Orders:</strong> {waiting_orders}</p>
    <p><strong>Preparing Orders:</strong> {preparing_orders}</p>
    <p><strong>Ready Orders:</strong> {ready_orders}</p>
    <p><strong>Callback Requests:</strong> {callback_orders}</p>
</div>"""
    
    html += """
<h3>Recent Orders</h3>
"""
    for order in orders[:5]:
        html += f"""
    <p>
        #{order.id}
        {"🚨 CALLBACK REQUEST" if order.status == "NEEDS_CALLBACK" else ""}
        — {order.status}
    </p>
    """

    html += """
    </body>
    </html>
    """

    db.close()
    return html

@app.get("/orders", response_class=HTMLResponse)
def orders_page():
    db = SessionLocal()
    orders = db.query(OrderDB).order_by(OrderDB.id.desc()).all()

    html = """
    <html>
    <head>

    <audio id="ding" preload="auto" src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg"></audio>

<script>
const newestOrder = "{orders[0].id if orders else 0}";
const lastSeen = localStorage.getItem("lastOrderId_orders");

if (lastSeen && newestOrder !== lastSeen) {
    localStorage.setItem("lastOrderId_orders", newestOrder);

    const ding = document.getElementById("ding");
    ding.volume = 0.4;
    ding.currentTime = 0;
    ding.play().finally(() => {
        setTimeout(() => location.reload(), 1000);
    });
} else {
    localStorage.setItem("lastOrderId_orders", newestOrder);
    setTimeout(() => location.reload(), 5000);
}
</script>

<style>
    body { font-family: Arial; padding:30px; background:#f7f7f7; }
.orders-grid { 
      display:grid; 
      grid-template-columns:repeat(4, 1fr); 
      gap:15px; 
}
.order-card { 
      background:white; 
      padding:18px; 
      border-radius:12px; 
      border:1px solid #ddd; 
      min-height:320px;
      }

button { margin:4px; 
      padding:8px 12px; 
      cursor:pointer; }
</style>
</head>
<body>

    <h1>📦 Orders</h1>
    <a href="/dashboard">← Back to Dashboard</a>
    <br><br>
    """
    html += '<div class="orders-grid">'

    for order in orders:
         html += f"""
    <div class="order-card">

        <h3>Order #{order.id}</h2>

        <p>
            <strong>{order.customer_name}</strong><br>
            {order.phone_number}
        </p>

        <p>
            <strong>Items:</strong><br>
            {str(order.items).replace(',', '<br>')}
        </p>

        <p>
            <strong>Notes:</strong><br>
            {order.notes or 'None'}
        </p>

        {"<div style='color:red;font-weight:bold;'>🚨 CALLBACK REQUEST</div>" if order.status == "NEEDS_CALLBACK" else ""}

        <p><strong>Status:</strong> {order.status}</p>

        {f'''
<form method="post" action="/orders/{order.id}/preparing" style="display:inline;">
    <button type="submit">Preparing</button>
</form>

<form method="post" action="/orders/{order.id}/cancel" style="display:inline;">
    <button type="submit">Cancel</button>
</form>
''' if order.status == "NEW" else ""}

{f'''
<form method="post" action="/orders/{order.id}/ready" style="display:inline;">
    <button type="submit">Ready</button>
</form>

<form method="post" action="/orders/{order.id}/cancel" style="display:inline;">
    <button type="submit">Cancel</button>
</form>
''' if order.status == "PREPARING" else ""}

{f'''
<p style="font-weight:bold;color:green;">✅ Ready</p>
''' if order.status == "READY" else ""}

{f'''
<p style="font-weight:bold;color:red;">❌ Cancelled</p>
''' if order.status == "CANCELLED" else ""}

    </div>
    """
    html += '</div>'

    html += """
    </body>
    </html>
    """

    db.close()
    return html

from typing import List

@app.post("/menu/upload")
def upload_menu(files: list[UploadFile] = File(None)):
    if not files:
        return {"error": "No files uploaded"}

    os.makedirs("uploaded_menus", exist_ok=True)

    for file in files:
        file_path = f"uploaded_menus/{file.filename}"

        with open(file_path, "wb") as f:
            f.write(file.file.read())

    return RedirectResponse(url="/menu", status_code=303)

from fastapi.responses import RedirectResponse
import os

@app.get("/menu/delete/{filename}")
def delete_menu(filename: str):
    file_path = os.path.join("uploaded_menus", filename)

    if os.path.exists(file_path):
        os.remove(file_path)

    return RedirectResponse(url="/menu", status_code=303)

@app.get("/menu", response_class=HTMLResponse)
def menu_page():
    uploaded_files = os.listdir("uploaded_menus") if os.path.exists("uploaded_menus") else []

    files_html = ""
    for f in uploaded_files:
        files_html += f"""
<div style="margin-bottom:10px;">
    {f}
    <a href="/uploaded_menus/{f}" target="_blank">View</a>
    |
    <a href="/menu/delete/{f}" style="color:red;">Delete</a>
</div>
"""
        
    html = f"""
    <html>
    <body style="font-family:Arial;padding:30px;">

<h1>📋 Menu</h1>

<a href="/dashboard">← Back to Dashboard</a>

<br><br>

<div style="background:white;padding:25px;border-radius:12px;border:1px solid #ddd;max-width:600px;">
    <h2>Upload Restaurant Menu</h2>

    <form method="post" action="/menu/upload" enctype="multipart/form-data">
        <input type="file" name="files" accept=".pdf,.jpg,.jpeg,.png" multiple required>
        <br><br>
        <button type="submit">Upload Menu</button>
    </form>

    <p style="color:#555;">Accepted: PDF, JPG, PNG</p>

    <h3>Uploaded Menus</h3>
<ul>
    {files_html}
</ul>

</body>
</html>
"""

    return html

@app.post("/orders/{order_id}/preparing")
def mark_order_preparing(order_id: int):

    db = SessionLocal()
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()

    if not order:
        db.close()
        return {"error": "Order not found"}

    order.status = "PREPARING"
    db.commit()
    db.refresh(order)

    log_event(
        "ORDER_PREPARING",
        f"Order #{order.id} started preparing"
    )

    db.close()

    return RedirectResponse(url="/orders", status_code=303)

@app.post("/orders/{order_id}/ready")
def mark_order_ready(order_id: int):
    
    db = SessionLocal()
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()

    if not order:
        db.close()
        return {"error": "Order not found"}

    order.status = "READY"
    db.commit()
    db.refresh(order)

    log_event(
    "ORDER_READY",
    f"Order #{order.id} marked ready"
)
    db.close()

    return RedirectResponse(url="/orders", status_code=303)

@app.post("/orders/{order_id}/cancel")
def mark_order_cancelled(order_id: int):
    db = SessionLocal()
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()

    if not order:
        db.close()
        return {"error": "Order not found"}

    order.status = "CANCELLED"
    db.commit()
    db.refresh(order)

    log_event(
        "ORDER_CANCELLED",
        f"Order #{order.id} cancelled"
    )

    db.close()

    return RedirectResponse(url="/orders", status_code=303)