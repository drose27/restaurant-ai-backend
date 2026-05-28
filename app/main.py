from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

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
        status="NEW"
    )

    db = SessionLocal()

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

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

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    db = SessionLocal()
    orders = db.query(OrderDB).order_by(OrderDB.id.desc()).all()
    db.close()

    html = """
    <html>
    <head>
        <title>Restaurant Orders</title>
        <style>
            body { font-family: Arial; padding: 30px; background: #f7f7f7; }
            h1 { color: #222; }
            .order {
                background: white;
                padding: 20px;
                margin-bottom: 15px;
                border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .new { color: green; font-weight: bold; }
        </style>
        <meta http-equiv="refresh" content="10">
    </head>
    <body>
        <h1>New Restaurant Orders</h1>
    """

    for order in orders:
        html += f"""
        <div class="order">
            <div class="new">NEW ORDER #{order.id}</div>
            <p><strong>Customer:</strong> {order.customer_name}</p>
            <p><strong>Phone:</strong> {order.phone_number}</p>
            <p><strong>Items:</strong> {order.items}</p>
            <p><strong>Notes:</strong> {order.notes}</p>
            <p><strong>Status:</strong> {order.status}</p>
            {f'''
<form method="post" action="/orders/{order.id}/ready">
    <button type="submit">Mark Ready</button>
</form>
''' if order.status != "READY" else ""}
            <p><strong>Total:</strong> ${order.total}</p>
        </div>
        """

    html += """
    </body>
    </html>
    """

    return html

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
    db.close()

    return {
        "success": True,
        "order_id": order_id,
        "status": "READY"
    }