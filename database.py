from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./supermarket.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    telegram_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, default="")
    phone = Column(String, nullable=True)
    role = Column(String, default="customer")  # super_admin, admin, worker, customer
    assigned_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    icon = Column(String, default="🛒")
    is_active = Column(Boolean, default=True)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, index=True)
    name = Column(String, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    price = Column(Float)  # Chegirmasiz asosiy sotuv narxi
    unit = Column(String, default="шт.")  # шт. yoki кг.
    is_weighted = Column(Boolean, default=False)
    stock = Column(Float, default=0.0)
    image_url = Column(String, default="https://placehold.co/300x300/f8f8f8/e52e2e?text=Mahsulot")
    is_approved = Column(Boolean, default=True)  # Ishchi qo'shsa False bo'ladi, Admin tasdiqlasa True
    created_by = Column(Integer, nullable=True)

class ProductRequest(Base):
    """Ishchilar tomonidan yuborilgan o'zgartirish yoki yangi mahsulot so'rovlari"""
    __tablename__ = "product_requests"
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("users.telegram_id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    product_id = Column(Integer, nullable=True)  # None bo'lsa yangi mahsulot, aks holda tahrirlash
    action = Column(String)  # "create", "update", "delete"
    name = Column(String)
    price = Column(Float)
    unit = Column(String, default="шт.")
    image_url = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_code = Column(String, unique=True, index=True)  # Masalan: #A72891
    user_id = Column(Integer, ForeignKey("users.telegram_id"))
    customer_phone = Column(String)
    items_json = Column(Text)  # Savatchadagi mahsulotlar ro'yxati
    total_amount = Column(Float)
    delivery_type = Column(String, default="pickup")  # pickup (Olib ketish) yoki delivery
    delivery_address = Column(String, nullable=True)
    status = Column(String, default="new")  # new, accepted, ready, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

class StoreSettings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, default=1)
    delivery_enabled = Column(Boolean, default=False)
    free_delivery_min_amount = Column(Float, default=500000.0)
    delivery_fee = Column(Float, default=15000.0)

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if not db.query(StoreSettings).first():
        db.add(StoreSettings(id=1, delivery_enabled=False, free_delivery_min_amount=500000.0, delivery_fee=15000.0))
        db.commit()
    db.close()
    
