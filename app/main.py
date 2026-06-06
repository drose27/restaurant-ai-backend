from fastapi import FastAPI
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

@app.get("/orders")
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

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    db = SessionLocal()

    orders = db.query(OrderDB).order_by(OrderDB.id.desc()).all()

    cutoff = datetime.now() - timedelta(hours=24)

    orders_today = [
        order for order in orders
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
<meta http-equiv="refresh" content="10">
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
    <h1>New Restaurant Orders</h1>
<div class="order">
    <h2>Today's Summary</h2>
    <p><strong>Orders Today:</strong> {orders_today_count}</p>
    <p><strong>Revenue Today:</strong> ${revenue_today:.2f}</p>
    <p><strong>Waiting Orders:</strong> {waiting_orders}</p>
    <p><strong>Preparing Orders:</strong> {preparing_orders}</p>
    <p><strong>Ready Orders:</strong> {ready_orders}</p>
    <p><strong>Callback Requests:</strong> {callback_orders}</p>
</div>"""
    
    for order in orders:
        html += f"""
        <div class="order">
            <div class="new">{"🚨 CALLBACK REQUEST" if order.status == "NEEDS_CALLBACK" else "NEW ORDER"} #{order.id}</div>
            <p><strong>Customer:</strong> {order.customer_name}</p>
            <p><strong>Phone:</strong> {order.phone_number}</p>
            <p><strong>Created:</strong> {order.created_at[11:16] if order.created_at else "No time"}</p>
            <p><strong>Items:</strong> {order.items}</p>
            <p><strong>Notes:</strong> {order.notes}</p>
            <p><strong>Status:</strong> {order.status}</p>
            {f'''
<form method="post" action="/orders/{order.id}/preparing">
    <button type="submit">Start Preparing</button>
</form>
''' if order.status == "NEW" else ""}      
{f'''
<form method="post" action="/orders/{order.id}/ready">
    <button type="submit">Mark Ready</button>
</form>
''' if order.status == "PREPARING" else ""}

<p><strong>Total:</strong> ${order.total}</p>
        </div>
        """

    html += """
    </body>
    </html>
    """

    db.close()
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

    return RedirectResponse(url="/dashboard", status_code=303)

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

    return RedirectResponse(url="/dashboard", status_code=303)
