from fastapi import FastAPI
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
        total=order.total
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